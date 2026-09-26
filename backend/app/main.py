from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker
from temporalio.client import Client

from .config import Settings, settings
from .database import Base, create_sqlite_engine, session_dependency
from .events import publish_order_event_async
from .models import AgentChangeDraft, AuditEvent, ChatConversation, ChatMessage, Email, OrderVersion, ProcessingRun, PurchaseOrder
from .realtime import relay_order_events
from .schemas import (
    AgentChangeDraftResponse,
    ChatConversationResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    OrderSnapshotInput,
    OrderSummaryResponse,
    OrderVersionResponse,
    ProcessingRunResponse,
    VersionDiffResponse,
)
from .services.diffs import version_diff
from .services.orders import append_version, get_order, order_query, summary_response, version_response
from .workflows import ChatRoutingWorkflow


class OrderConnections:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}

    async def connect(self, order_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(order_id, set()).add(websocket)

    def disconnect(self, order_id: int, websocket: WebSocket) -> None:
        self._connections.get(order_id, set()).discard(websocket)

    async def publish(self, order_id: int, event: dict) -> None:
        for websocket in list(self._connections.get(order_id, set())):
            try:
                await websocket.send_json(event)
            except (RuntimeError, WebSocketDisconnect):
                self.disconnect(order_id, websocket)


def chat_message_response(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse.model_validate(message)


def draft_response(draft: AgentChangeDraft) -> AgentChangeDraftResponse:
    return AgentChangeDraftResponse(
        id=draft.id,
        order_id=draft.order_id,
        chat_message_id=draft.chat_message_id,
        base_version_id=draft.base_version_id,
        proposed_snapshot=OrderSnapshotInput.model_validate_json(draft.proposed_snapshot_json),
        status=draft.status,
        resolved_at=draft.resolved_at,
        created_at=draft.created_at,
    )


def create_app(app_settings: Settings = settings) -> FastAPI:
    engine = create_sqlite_engine(Path(app_settings.database_path))
    factory = sessionmaker(engine, expire_on_commit=False)
    connections = OrderConnections()

    async def emit_order_event(order_id: int, event: dict) -> None:
        """Publish through Redis; retain local WebSocket delivery during a Redis outage."""
        published = await publish_order_event_async(order_id, event, app_settings.redis_url)
        if not published:
            await connections.publish(order_id, event)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(engine)
        relay_stop = asyncio.Event()
        relay_task = asyncio.create_task(relay_order_events(app_settings.redis_url, connections.publish, relay_stop))
        try:
            yield
        finally:
            relay_stop.set()
            relay_task.cancel()
            with suppress(asyncio.CancelledError):
                await relay_task
            engine.dispose()

    app = FastAPI(title="Procurement Assistant API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def session() -> Session:
        yield from session_dependency(factory)

    @app.get("/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/orders", response_model=list[OrderSummaryResponse])
    def list_orders(db: Session = Depends(session)) -> list[OrderSummaryResponse]:
        orders = db.scalars(order_query().order_by(PurchaseOrder.updated_at.desc())).unique().all()
        return [summary_response(order) for order in orders]

    @app.get("/orders/{order_id}", response_model=OrderVersionResponse)
    def read_order(order_id: int, db: Session = Depends(session)) -> OrderVersionResponse:
        order = get_order(db, order_id)
        if order.current_version is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Purchase order is still being processed")
        return version_response(order.current_version)

    @app.get("/orders/{order_id}/versions", response_model=list[OrderVersionResponse])
    def list_versions(order_id: int, db: Session = Depends(session)) -> list[OrderVersionResponse]:
        order = get_order(db, order_id)
        return [version_response(version) for version in sorted(order.versions, key=lambda value: value.version_number, reverse=True)]


    @app.get("/orders/{order_id}/processing-runs", response_model=list[ProcessingRunResponse])
    def list_processing_runs(order_id: int, db: Session = Depends(session)) -> list[ProcessingRunResponse]:
        order = get_order(db, order_id)
        runs = db.scalars(
            select(ProcessingRun)
            .join(Email, ProcessingRun.email_id == Email.id)
            .where(Email.thread_id == order.thread_id)
            .order_by(ProcessingRun.created_at.desc())
        ).all()
        return [
            ProcessingRunResponse(
                id=run.id,
                email_id=run.email_id,
                attachment_id=run.attachment_id,
                temporal_workflow_id=run.temporal_workflow_id,
                status=run.status,
                stage=run.stage,
                error_summary=run.error_summary,
                completed_at=run.completed_at,
                created_at=run.created_at,
            )
            for run in runs
        ]

    @app.get("/orders/{order_id}/versions/{version_id}/diff", response_model=VersionDiffResponse)
    def compare_versions(order_id: int, version_id: int, base_version_id: int, db: Session = Depends(session)) -> VersionDiffResponse:
        order = get_order(db, order_id)
        versions = {version.id: version for version in order.versions}
        base = versions.get(base_version_id)
        target = versions.get(version_id)
        if base is None or target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order version not found")
        return version_diff(base, target)
    @app.post("/orders/{order_id}/versions", response_model=OrderVersionResponse, status_code=status.HTTP_201_CREATED)
    async def save_manual_version(order_id: int, payload: OrderSnapshotInput, db: Session = Depends(session)) -> OrderVersionResponse:
        order = get_order(db, order_id)
        version = append_version(session=db, order=order, snapshot=payload, source_type="manual_edit", actor_type="human")
        db.commit()
        response = version_response(version)
        await emit_order_event(order_id, {"type": "order.version_created", "version_id": version.id})
        return response

    @app.get("/orders/{order_id}/chat/conversations", response_model=list[ChatConversationResponse])
    def list_chat_conversations(order_id: int, db: Session = Depends(session)) -> list[ChatConversationResponse]:
        get_order(db, order_id)
        conversations = db.scalars(
            select(ChatConversation)
            .where(ChatConversation.order_id == order_id)
            .options(selectinload(ChatConversation.messages))
            .order_by(ChatConversation.updated_at.desc())
        ).all()
        return [
            ChatConversationResponse(
                id=conversation.id,
                order_id=conversation.order_id,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
                messages=[chat_message_response(message) for message in conversation.messages],
            )
            for conversation in conversations
        ]

    @app.post("/orders/{order_id}/chat/messages", response_model=ChatMessageResponse, status_code=status.HTTP_202_ACCEPTED)
    async def create_chat_message(order_id: int, payload: ChatMessageCreate, db: Session = Depends(session)) -> ChatMessageResponse:
        get_order(db, order_id)
        conversation = None
        if payload.conversation_id is not None:
            conversation = db.scalar(
                select(ChatConversation).where(ChatConversation.id == payload.conversation_id, ChatConversation.order_id == order_id)
            )
        if conversation is None:
            conversation = ChatConversation(order_id=order_id)
            db.add(conversation)
            db.flush()
        message = ChatMessage(conversation_id=conversation.id, sender_type="human", message_type="request", content=payload.content)
        db.add(message)
        db.commit()
        db.refresh(message)
        workflow_id = f"procurement-chat-{message.id}"
        try:
            client = await Client.connect(app_settings.temporal_address)
            await client.start_workflow(
                ChatRoutingWorkflow.run,
                args=[message.id, str(app_settings.database_path)],
                id=workflow_id,
                task_queue=app_settings.temporal_task_queue,
            )
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chat workflow could not be started") from error
        message.temporal_workflow_id = workflow_id
        db.commit()
        db.refresh(message)
        response = chat_message_response(message)
        await emit_order_event(order_id, {"type": "chat.message_created", "message_id": message.id})
        return response

    @app.get("/orders/{order_id}/change-drafts", response_model=list[AgentChangeDraftResponse])
    def list_change_drafts(order_id: int, db: Session = Depends(session)) -> list[AgentChangeDraftResponse]:
        get_order(db, order_id)
        drafts = db.scalars(
            select(AgentChangeDraft)
            .where(AgentChangeDraft.order_id == order_id)
            .order_by(AgentChangeDraft.created_at.desc())
        ).all()
        return [draft_response(draft) for draft in drafts]

    @app.post("/orders/{order_id}/change-drafts/{draft_id}/accept", response_model=OrderVersionResponse)
    async def accept_change_draft(order_id: int, draft_id: int, db: Session = Depends(session)) -> OrderVersionResponse:
        order = get_order(db, order_id)
        draft = db.scalar(select(AgentChangeDraft).where(AgentChangeDraft.id == draft_id, AgentChangeDraft.order_id == order_id))
        if draft is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change draft not found")
        if draft.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Change draft has already been resolved")
        if order.current_version_id != draft.base_version_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Change draft is based on an outdated order version")
        snapshot = OrderSnapshotInput.model_validate_json(draft.proposed_snapshot_json)
        version = append_version(
            session=db,
            order=order,
            snapshot=snapshot,
            source_type="agent_change_draft",
            actor_type="agent",
            audit_action="change_draft.accepted_as_version",
        )
        draft.status = "accepted"
        draft.resolved_at = datetime.now(UTC)
        db.add(
            AuditEvent(
                order_id=order.id,
                order_version_id=version.id,
                agent_change_draft_id=draft.id,
                actor_type="human",
                action="change_draft.accepted",
            )
        )
        db.commit()
        response = version_response(version)
        await emit_order_event(order_id, {"type": "change_draft.accepted", "draft_id": draft.id, "version_id": version.id})
        return response

    @app.post("/orders/{order_id}/change-drafts/{draft_id}/discard", response_model=AgentChangeDraftResponse)
    async def discard_change_draft(order_id: int, draft_id: int, db: Session = Depends(session)) -> AgentChangeDraftResponse:
        get_order(db, order_id)
        draft = db.scalar(select(AgentChangeDraft).where(AgentChangeDraft.id == draft_id, AgentChangeDraft.order_id == order_id))
        if draft is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Change draft not found")
        if draft.status != "pending":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Change draft has already been resolved")
        draft.status = "discarded"
        draft.resolved_at = datetime.now(UTC)
        db.add(AuditEvent(order_id=order_id, agent_change_draft_id=draft.id, actor_type="human", action="change_draft.discarded"))
        db.commit()
        response = draft_response(draft)
        await emit_order_event(order_id, {"type": "change_draft.discarded", "draft_id": draft.id})
        return response

    @app.websocket("/ws/orders/{order_id}")
    async def order_events(order_id: int, websocket: WebSocket) -> None:
        await connections.connect(order_id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            connections.disconnect(order_id, websocket)

    return app


app = create_app()