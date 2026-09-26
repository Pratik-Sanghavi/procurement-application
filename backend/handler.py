"""Thin simulator adapter that dispatches persisted email events to Temporal."""

import asyncio
from pathlib import Path

from temporalio.client import Client

try:
    from app.config import Settings
    from app.workflows import PurchaseOrderProcessingWorkflow
except ModuleNotFoundError:
    from backend.app.config import Settings
    from backend.app.workflows import PurchaseOrderProcessingWorkflow


def handle_event(event_type: str, record_id: int, db_path: Path) -> None:
    """Dispatch a committed simulator event; worker activities perform all processing."""
    if event_type != "email.received":
        raise ValueError(f"Unsupported event type: {event_type}")
    asyncio.run(_run_email_workflow(record_id, db_path.resolve()))


async def _run_email_workflow(email_id: int, db_path: Path) -> None:
    runtime_settings = Settings(database_path=db_path)
    client = await Client.connect(runtime_settings.temporal_address)
    await client.execute_workflow(
        PurchaseOrderProcessingWorkflow.run,
        args=[email_id, str(db_path)],
        id=f"procurement-email-{email_id}",
        task_queue=runtime_settings.temporal_task_queue,
    )