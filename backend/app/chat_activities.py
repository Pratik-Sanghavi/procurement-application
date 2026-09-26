from __future__ import annotations

import json
from pathlib import Path

from openai import OpenAI
from sqlalchemy import select
from temporalio import activity

from .config import Settings
from .database import session_factory
from .events import publish_order_event
from .jev import JevClient
from .models import AgentChangeDraft, AuditEvent, ChatConversation, ChatMessage, OrderVersion, PurchaseOrder
from .schemas import OrderSnapshotInput
from .services.orders import version_response


def _settings() -> Settings:
    return Settings()


def _message_context(session, message_id: int):  # type: ignore[no-untyped-def]
    message = session.get(ChatMessage, message_id)
    if message is None:
        raise ValueError(f"Chat message {message_id} does not exist")
    conversation = session.get(ChatConversation, message.conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation for chat message {message_id} does not exist")
    order = session.get(PurchaseOrder, conversation.order_id)
    if order is None or order.current_version_id is None:
        raise ValueError("Purchase order has no current version")
    version = session.get(OrderVersion, order.current_version_id)
    if version is None:
        raise ValueError("Current purchase-order version does not exist")
    return message, conversation, order, version


@activity.defn
def classify_chat_intent(message_id: int, database_path: str) -> dict:
    settings = _settings()
    if not settings.typesafe_api_key:
        raise RuntimeError("TYPESAFE_API_KEY is required to route chat messages")
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        message = session.get(ChatMessage, message_id)
        if message is None:
            raise ValueError(f"Chat message {message_id} does not exist")
        conversation = session.get(ChatConversation, message.conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation for chat message {message_id} does not exist")
        decision = JevClient(
            api_key=settings.typesafe_api_key,
            model=settings.typesafe_model,
            timeout_seconds=settings.typesafe_timeout_seconds,
        ).classify_chat_intent(message.content)
        message.intent = decision.intent
        session.add(
            AuditEvent(
                order_id=conversation.order_id,
                chat_message_id=message.id,
                actor_type="agent",
                action="chat.intent_classified",
                change_summary_json=json.dumps(
                    {"intent": decision.intent, "confidence": decision.confidence, "receipt": decision.raw_response}
                ),
            )
        )
        result = {"order_id": conversation.order_id, "intent": decision.intent, "confidence": decision.confidence}
    publish_order_event(result["order_id"], {"type": "chat.intent_classified", "message_id": message_id, "intent": result["intent"]})
    return {"intent": result["intent"], "confidence": result["confidence"]}


@activity.defn
def answer_order_question(message_id: int, database_path: str) -> dict[str, int]:
    settings = _settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to answer order questions")
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        message, conversation, order, version = _message_context(session, message_id)
        snapshot_json = version_response(version).model_dump_json()
        completion = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_extraction_model,
            messages=[
                {"role": "system", "content": "Answer only from the supplied purchase-order snapshot. State clearly when information is unavailable."},
                {"role": "user", "content": f"Purchase-order snapshot:\n{snapshot_json}\n\nQuestion: {message.content}"},
            ],
        )
        answer = completion.choices[0].message.content or "I could not produce an answer from this order."
        response = ChatMessage(
            conversation_id=conversation.id,
            reply_to_message_id=message.id,
            sender_type="agent",
            message_type="answer",
            content=answer,
            intent="question",
        )
        session.add(response)
        session.flush()
        result = {"order_id": order.id, "response_message_id": response.id}
    publish_order_event(result["order_id"], {"type": "chat.response_created", "message_id": result["response_message_id"]})
    return {"response_message_id": result["response_message_id"]}


@activity.defn
def propose_order_change(message_id: int, database_path: str) -> dict[str, int]:
    settings = _settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to propose order changes")
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        message, conversation, order, version = _message_context(session, message_id)
        current_snapshot = version_response(version).model_dump_json()
        completion = OpenAI(api_key=settings.openai_api_key).beta.chat.completions.parse(
            model=settings.openai_extraction_model,
            messages=[
                {"role": "system", "content": "Return a complete updated purchase-order snapshot. Apply only the explicitly requested change; preserve all other current values."},
                {"role": "user", "content": f"Current snapshot:\n{current_snapshot}\n\nRequested change: {message.content}"},
            ],
            response_format=OrderSnapshotInput,
        )
        proposal = completion.choices[0].message.parsed
        if proposal is None:
            raise ValueError("OpenAI did not return a structured change proposal")
        if proposal.supplier_order_number != order.supplier_order_number:
            raise ValueError("Change proposal cannot alter the supplier order number")
        response = ChatMessage(
            conversation_id=conversation.id,
            reply_to_message_id=message.id,
            sender_type="agent",
            message_type="change_proposal",
            content="I prepared a proposed order update. Review the highlighted changes and accept or discard it.",
            intent="change_request",
        )
        session.add(response)
        session.flush()
        draft = AgentChangeDraft(
            order_id=order.id,
            chat_message_id=response.id,
            base_version_id=version.id,
            proposed_snapshot_json=proposal.model_dump_json(),
        )
        session.add(draft)
        session.flush()
        session.add(
            AuditEvent(
                order_id=order.id,
                chat_message_id=response.id,
                agent_change_draft_id=draft.id,
                actor_type="agent",
                action="change_draft.proposed",
                change_summary_json=json.dumps({"base_version_id": version.id}),
            )
        )
        result = {"order_id": order.id, "response_message_id": response.id, "draft_id": draft.id}
    publish_order_event(
        result["order_id"],
        {"type": "change_draft.created", "message_id": result["response_message_id"], "draft_id": result["draft_id"]},
    )
    return {"response_message_id": result["response_message_id"], "draft_id": result["draft_id"]}


@activity.defn
def respond_to_unsupported_request(message_id: int, database_path: str) -> dict[str, int]:
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        message, conversation, order, _ = _message_context(session, message_id)
        response = ChatMessage(
            conversation_id=conversation.id,
            reply_to_message_id=message.id,
            sender_type="agent",
            message_type="answer",
            content="I can answer questions about this purchase order or prepare a proposed order change.",
            intent="other",
        )
        session.add(response)
        session.flush()
        result = {"order_id": order.id, "response_message_id": response.id}
    publish_order_event(result["order_id"], {"type": "chat.response_created", "message_id": result["response_message_id"]})
    return {"response_message_id": result["response_message_id"]}