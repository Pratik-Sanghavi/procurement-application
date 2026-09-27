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
from .schemas import LineItemData, OrderChangePlan, OrderSnapshotInput
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
        if message.intent is not None:
            return {"intent": message.intent, "confidence": None}
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
        existing = session.scalar(select(ChatMessage).where(ChatMessage.reply_to_message_id == message.id, ChatMessage.message_type == "answer", ChatMessage.intent == "question"))
        if existing is not None:
            return {"response_message_id": existing.id}
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


def _apply_change_plan(snapshot: OrderSnapshotInput, plan: OrderChangePlan) -> OrderSnapshotInput:
    """Apply only whitelisted, explicit model-proposed updates to a snapshot."""
    payload = snapshot.model_dump(mode="json")
    for update in plan.order_updates:
        allowed_fields = getattr(snapshot, update.section).model_fields
        if update.field not in allowed_fields:
            raise ValueError(f"Unsupported order field in change proposal: {update.section}.{update.field}")
        payload[update.section][update.field] = update.value

    line_items = {item["line_number"]: item for item in payload["line_items"]}
    for update in plan.line_item_updates:
        item = line_items.get(update.line_number)
        if item is None:
            raise ValueError(f"Change proposal references unknown line item {update.line_number}")
        if update.field not in LineItemData.model_fields or update.field in {"line_number", "description"}:
            raise ValueError(f"Unsupported line-item field in change proposal: {update.field}")
        item[update.field] = update.value

    if not plan.order_updates and not plan.line_item_updates:
        raise ValueError("The requested change did not identify a supported order field")
    return OrderSnapshotInput.model_validate(payload)


@activity.defn
def propose_order_change(message_id: int, database_path: str) -> dict[str, int]:
    settings = _settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to propose order changes")
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        message, conversation, order, version = _message_context(session, message_id)
        existing_response = session.scalar(select(ChatMessage).where(ChatMessage.reply_to_message_id == message.id, ChatMessage.message_type == "change_proposal"))
        if existing_response is not None:
            existing_draft = session.scalar(select(AgentChangeDraft).where(AgentChangeDraft.chat_message_id == existing_response.id))
            if existing_draft is not None:
                return {"response_message_id": existing_response.id, "draft_id": existing_draft.id}

        current_snapshot = OrderSnapshotInput.model_validate(version_response(version).model_dump(mode="json"))
        completion = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
            model=settings.openai_change_model,
            max_completion_tokens=8_192,
            reasoning_effort="low",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Translate the user's request into a compact JSON patch for the supplied purchase order. Return exactly {\"order_updates\": [], \"line_item_updates\": []}. Each order update is {\"section\": one of supplier/details/shipping/financial_summary, \"field\": field name, \"value\": string or null}. Each line-item update is {\"line_number\": integer, \"field\": one of size/ordered_quantity/confirmed_quantity/catalog_price/customer_price/variety_license_fee/extended_line_amount/item_notes/scheduled_shipping_date_or_week, \"value\": string or null}. Use line_number only from the supplied snapshot. Propose only explicitly requested changes. Do not return a complete snapshot, explanations, or unrequested updates."},
                {"role": "user", "content": f"Current snapshot:\n{current_snapshot.model_dump_json()}\n\nRequested change: {message.content}"},
            ],
        )
        content = completion.choices[0].message.content
        if not content:
            raise ValueError("OpenAI did not return a change patch")
        proposal = _apply_change_plan(current_snapshot, OrderChangePlan.model_validate_json(content))
        response = ChatMessage(conversation_id=conversation.id, reply_to_message_id=message.id, sender_type="agent", message_type="change_proposal", content="I prepared a proposed order update. Review the highlighted changes and accept or discard it.", intent="change_request")
        session.add(response)
        session.flush()
        draft = AgentChangeDraft(order_id=order.id, chat_message_id=response.id, base_version_id=version.id, proposed_snapshot_json=proposal.model_dump_json())
        session.add(draft)
        session.flush()
        session.add(AuditEvent(order_id=order.id, chat_message_id=response.id, agent_change_draft_id=draft.id, actor_type="agent", action="change_draft.proposed", change_summary_json=json.dumps({"base_version_id": version.id})))
        result = {"order_id": order.id, "response_message_id": response.id, "draft_id": draft.id}
    publish_order_event(result["order_id"], {"type": "change_draft.created", "message_id": result["response_message_id"], "draft_id": result["draft_id"]})
    return {"response_message_id": result["response_message_id"], "draft_id": result["draft_id"]}

@activity.defn
def respond_to_unsupported_request(message_id: int, database_path: str) -> dict[str, int]:
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        message, conversation, order, _ = _message_context(session, message_id)
        existing = session.scalar(select(ChatMessage).where(ChatMessage.reply_to_message_id == message.id, ChatMessage.message_type == "answer", ChatMessage.intent == "other"))
        if existing is not None:
            return {"response_message_id": existing.id}
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