from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI
from pypdf import PdfReader
from sqlalchemy import select
from temporalio import activity

from .config import Settings
from .database import session_factory
from .events import publish_order_event
from .models import Attachment, Email, OrderVersion, ProcessingRun, PurchaseOrder
from .schemas import FinancialSummaryData, LineItemData, OrderDetailsData, OrderSnapshotChunk, OrderSnapshotInput, ShippingData, SupplierData
from .services.orders import append_version


def _settings() -> Settings:
    return Settings()


@activity.defn
def create_processing_run(email_id: int, workflow_id: str, database_path: str) -> dict[str, int]:
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        email = session.get(Email, email_id)
        if email is None:
            raise ValueError(f"Email {email_id} does not exist")
        attachment = session.scalar(select(Attachment).where(Attachment.email_id == email_id).order_by(Attachment.id))
        if attachment is None:
            raise ValueError(f"Email {email_id} has no PDF attachment")
        run = session.scalar(select(ProcessingRun).where(ProcessingRun.temporal_workflow_id == workflow_id))
        if run is None:
            run = ProcessingRun(
                email_id=email_id,
                attachment_id=attachment.id,
                temporal_workflow_id=workflow_id,
                status="running",
                stage="source_loaded",
            )
            session.add(run)
            session.flush()
        return {"processing_run_id": run.id, "attachment_id": attachment.id}


@activity.defn
def extract_pdf_text(attachment_id: int, database_path: str) -> str:
    factory = session_factory(Path(database_path))
    with factory() as session:
        attachment = session.get(Attachment, attachment_id)
        if attachment is None:
            raise ValueError(f"Attachment {attachment_id} does not exist")
        reader = PdfReader(io.BytesIO(attachment.content))
        text = "\n\n".join(page.extract_text(extraction_mode="layout") or "" for page in reader.pages).strip()
        if not text:
            raise ValueError("PDF has no extractable text; OCR is not enabled")
        return text


@activity.defn
def extract_order_snapshot(pdf_text: str) -> dict:
    settings = _settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to process purchase-order PDFs")
    client = OpenAI(api_key=settings.openai_api_key)
    completion = client.beta.chat.completions.parse(
        model=settings.openai_extraction_model,
        max_completion_tokens=32_768,
        reasoning_effort="low",
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract a supplier purchase-order acknowledgement into the supplied schema. "
                    "Use only information stated in the document. Preserve every line item. "
                    "Extract document-level financial totals when the acknowledgement provides them, including plant cost, variety license fee total, container cost, label cost, freight, and grand total. "
                    "Supplier order number is required. Use null for unavailable optional values."
                ),
            },
            {"role": "user", "content": pdf_text},
        ],
        response_format=OrderSnapshotInput,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("OpenAI did not return a structured purchase order")
    return parsed.model_dump(mode="json")


@activity.defn
def extract_pdf_text_chunks(attachment_id: int, database_path: str) -> list[str]:
    """Extract PDF pages into bounded text sections for reliable structured output."""
    factory = session_factory(Path(database_path))
    with factory() as session:
        attachment = session.get(Attachment, attachment_id)
        if attachment is None:
            raise ValueError(f"Attachment {attachment_id} does not exist")
        reader = PdfReader(io.BytesIO(attachment.content))
        pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    max_chunk_characters = 2_000
    chunks: list[str] = []
    for page_number, page_text in enumerate(pages, start=1):
        text = page_text.strip()
        if not text:
            continue
        page_prefix = f"--- Page {page_number} ---\n"
        while text:
            available = max_chunk_characters - len(page_prefix)
            if len(text) <= available:
                chunks.append(page_prefix + text)
                break
            split_at = text.rfind("\n", 0, available)
            if split_at <= available // 2:
                split_at = available
            chunks.append(page_prefix + text[:split_at].strip())
            text = text[split_at:].lstrip()
    if not chunks:
        raise ValueError("PDF has no extractable text; OCR is not enabled")
    return chunks


@activity.defn
def extract_order_snapshot_chunk(pdf_text: str) -> dict:
    """Extract one permissive partial snapshot; `{}` is valid for non-data sections."""
    settings = _settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to process purchase-order PDFs")
    completion = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
        model=settings.openai_chunk_extraction_model,
        max_tokens=4_096,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract facts from this one purchase-order acknowledgement section. "
                    "Return only a JSON object. Omit fields that are not explicitly present. "
                    "If this section has no useful order facts, return {}. "
                    "Allowed top-level fields are supplier_order_number, supplier, details, shipping, "
                    "financial_summary, and line_items. supplier requires name when present. "
                    "Each line item requires line_number and description; optional item fields are size, "
                    "ordered_quantity, confirmed_quantity, catalog_price, customer_price, "
                    "variety_license_fee, extended_line_amount, item_notes, and scheduled_shipping_date_or_week. "
                    "Do not invent facts and do not repeat rows from other sections."
                ),
            },
            {"role": "user", "content": pdf_text},
        ],
        response_format={"type": "json_object"},
    )
    content = completion.choices[0].message.content
    if not content:
        raise ValueError("OpenAI did not return a JSON purchase-order section")
    raw = json.loads(content)
    if not isinstance(raw, dict):
        raise ValueError("OpenAI returned a non-object purchase-order section")

    normalized: dict = {}
    supplier_order_number = raw.get("supplier_order_number")
    if isinstance(supplier_order_number, str) and supplier_order_number.strip():
        normalized["supplier_order_number"] = supplier_order_number.strip()
    for field_name, model in (
        ("supplier", SupplierData),
        ("details", OrderDetailsData),
        ("shipping", ShippingData),
        ("financial_summary", FinancialSummaryData),
    ):
        value = raw.get(field_name)
        if not isinstance(value, dict):
            continue
        try:
            normalized[field_name] = model.model_validate(value)
        except ValueError:
            continue

    line_items: list[LineItemData] = []
    values = raw.get("line_items", [])
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, dict):
            continue
        item = dict(value)
        if isinstance(item.get("item_notes"), list):
            item["item_notes"] = "\n".join(str(note) for note in item["item_notes"])
        try:
            line_items.append(LineItemData.model_validate(item))
        except ValueError:
            continue
    normalized["line_items"] = line_items
    return OrderSnapshotChunk.model_validate(normalized).model_dump(mode="json")


def _merge_fields(parts: list[OrderSnapshotChunk], key: str, model: type) -> dict:
    merged: dict = {}
    for field_name in model.model_fields:
        for part in parts:
            nested = getattr(part, key)
            value = getattr(nested, field_name) if nested is not None else None
            if value is not None and value != "":
                merged[field_name] = value
                break
    return merged


@activity.defn
def stitch_order_snapshot(chunk_data: list[dict]) -> dict:
    """Merge partial extractions deterministically and validate one complete snapshot."""
    parts = [OrderSnapshotChunk.model_validate(chunk) for chunk in chunk_data]
    supplier_order_number = next((part.supplier_order_number for part in parts if part.supplier_order_number), None)
    supplier_values = _merge_fields(parts, "supplier", SupplierData)
    if not supplier_order_number or not supplier_values.get("name"):
        raise ValueError("Acknowledgement sections did not provide supplier order number and supplier name")
    items_by_number: dict[int, LineItemData] = {}
    for part in parts:
        for item in part.line_items:
            existing = items_by_number.get(item.line_number)
            if existing is None:
                items_by_number[item.line_number] = item
                continue
            combined = existing.model_dump()
            for field_name, value in item.model_dump().items():
                if field_name != "line_number" and value is not None and combined.get(field_name) is None:
                    combined[field_name] = value
            items_by_number[item.line_number] = LineItemData.model_validate(combined)
    snapshot = OrderSnapshotInput(
        supplier_order_number=supplier_order_number,
        supplier=SupplierData(**supplier_values),
        details=OrderDetailsData(**_merge_fields(parts, "details", OrderDetailsData)),
        shipping=ShippingData(**_merge_fields(parts, "shipping", ShippingData)),
        financial_summary=FinancialSummaryData(**_merge_fields(parts, "financial_summary", FinancialSummaryData)),
        line_items=[items_by_number[number] for number in sorted(items_by_number)],
    )
    return snapshot.model_dump(mode="json")

@activity.defn
def validate_order_snapshot(snapshot_data: dict) -> dict:
    """Reject structurally incomplete extractions before any order data is written."""
    snapshot = OrderSnapshotInput.model_validate(snapshot_data)
    return snapshot.model_dump(mode="json")

@activity.defn
def persist_supplier_version(email_id: int, processing_run_id: int, snapshot_data: dict, database_path: str) -> dict[str, int]:
    """Persist exactly one order version per source email despite activity retries."""
    snapshot = OrderSnapshotInput.model_validate(snapshot_data)
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        email = session.get(Email, email_id)
        if email is None:
            raise ValueError(f"Email {email_id} does not exist")
        existing = session.scalar(select(OrderVersion).where(OrderVersion.source_email_id == email_id))
        if existing is not None:
            result = {"order_id": existing.order_id, "version_id": existing.id}
        else:
            order = session.scalar(select(PurchaseOrder).where(PurchaseOrder.supplier_order_number == snapshot.supplier_order_number))
            if order is None:
                order = PurchaseOrder(thread_id=email.thread_id, supplier_order_number=snapshot.supplier_order_number)
                session.add(order)
                session.flush()
            version = append_version(
                session,
                order=order,
                snapshot=snapshot,
                source_type="supplier_acknowledgement",
                actor_type="agent",
                source_email_id=email_id,
                audit_action="supplier_acknowledgement.processed",
            )
            result = {"order_id": order.id, "version_id": version.id}
        run = session.get(ProcessingRun, processing_run_id)
        if run is not None:
            run.status = "completed"
            run.stage = "persisted"
            run.completed_at = datetime.now(UTC)
    publish_order_event(result["order_id"], {"type": "order.version_created", "version_id": result["version_id"]})
    return result

@activity.defn
def mark_processing_failed(processing_run_id: int, error_summary: str, database_path: str) -> None:
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        run = session.get(ProcessingRun, processing_run_id)
        if run is None:
            return
        run.status = "failed"
        run.stage = "failed"
        run.error_summary = error_summary[:2_000]
        run.completed_at = datetime.now(UTC)
        email = session.get(Email, run.email_id)
        order_id = session.scalar(select(PurchaseOrder.id).where(PurchaseOrder.thread_id == email.thread_id)) if email else None
    if order_id is not None:
        publish_order_event(order_id, {"type": "processing.failed", "processing_run_id": processing_run_id})


@activity.defn
def set_processing_stage(processing_run_id: int, stage: str, database_path: str) -> None:
    """Persist an observable workflow stage and notify an already-known order."""
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        run = session.get(ProcessingRun, processing_run_id)
        if run is None:
            raise ValueError(f"Processing run {processing_run_id} does not exist")
        run.status = "running"
        run.stage = stage
        email = session.get(Email, run.email_id)
        order_id = session.scalar(select(PurchaseOrder.id).where(PurchaseOrder.thread_id == email.thread_id)) if email else None
    if order_id is not None:
        publish_order_event(order_id, {"type": "processing.stage_changed", "processing_run_id": processing_run_id, "stage": stage})