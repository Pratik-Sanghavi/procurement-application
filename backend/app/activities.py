from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI
from pypdf import PdfReader
from sqlalchemy import select
from temporalio import activity

from .config import Settings
from .database import session_factory
from .models import Attachment, Email, ProcessingRun, PurchaseOrder
from .schemas import OrderSnapshotInput
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
def persist_supplier_version(email_id: int, processing_run_id: int, snapshot_data: dict, database_path: str) -> dict[str, int]:
    snapshot = OrderSnapshotInput.model_validate(snapshot_data)
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        email = session.get(Email, email_id)
        if email is None:
            raise ValueError(f"Email {email_id} does not exist")
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
        run = session.get(ProcessingRun, processing_run_id)
        if run is not None:
            run.status = "completed"
            run.stage = "persisted"
            run.completed_at = datetime.now(UTC)
        return {"order_id": order.id, "version_id": version.id}


@activity.defn
def mark_processing_failed(processing_run_id: int, error_summary: str, database_path: str) -> None:
    factory = session_factory(Path(database_path))
    with factory.begin() as session:
        run = session.get(ProcessingRun, processing_run_id)
        if run is not None:
            run.status = "failed"
            run.stage = "failed"
            run.error_summary = error_summary[:2_000]
            run.completed_at = datetime.now(UTC)
