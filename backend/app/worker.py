import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import create_processing_run, extract_order_snapshot_chunk, extract_pdf_text_chunks, mark_processing_failed, persist_supplier_version, set_processing_stage, stitch_order_snapshot, validate_order_snapshot
from .chat_activities import answer_order_question, classify_chat_intent, propose_order_change, respond_to_unsupported_request
from .config import settings
from .workflows import ChatRoutingWorkflow, OrderChangeRequestWorkflow, OrderQuestionWorkflow, PurchaseOrderProcessingWorkflow


async def run_worker() -> None:
    client = await Client.connect(settings.temporal_address)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[PurchaseOrderProcessingWorkflow, ChatRoutingWorkflow, OrderQuestionWorkflow, OrderChangeRequestWorkflow],
        activity_executor=ThreadPoolExecutor(
            max_workers=8,
            thread_name_prefix="procurement-activity",
        ),
        activities=[
            create_processing_run,
            extract_pdf_text_chunks,
            extract_order_snapshot_chunk,
            stitch_order_snapshot,
            validate_order_snapshot,
            set_processing_stage,
            persist_supplier_version,
            mark_processing_failed,
            classify_chat_intent,
            answer_order_question,
            propose_order_change,
            respond_to_unsupported_request,
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())