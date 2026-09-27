import asyncio
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from .activities import (
        create_processing_run,
        extract_order_snapshot_chunk,
        extract_pdf_text_chunks,
        mark_processing_failed,
        persist_supplier_version,
        set_processing_stage,
        stitch_order_snapshot,
        validate_order_snapshot,
    )
    from .chat_activities import answer_order_question, classify_chat_intent, propose_order_change, respond_to_unsupported_request


@workflow.defn
class PurchaseOrderProcessingWorkflow:
    @workflow.run
    async def run(self, email_id: int, database_path: str) -> dict[str, int]:
        run = await workflow.execute_activity(
            create_processing_run,
            args=[email_id, workflow.info().workflow_id, database_path],
            start_to_close_timeout=timedelta(seconds=30),
        )
        try:
            chunks = await workflow.execute_activity(
                extract_pdf_text_chunks,
                args=[run["attachment_id"], database_path],
                start_to_close_timeout=timedelta(minutes=2),
            )
            await workflow.execute_activity(
                set_processing_stage,
                args=[run["processing_run_id"], "pdf_text_chunked", database_path],
                start_to_close_timeout=timedelta(seconds=30),
            )
            partial_snapshots: list[dict] = []
            batch_size = 4
            for batch_start in range(0, len(chunks), batch_size):
                batch = chunks[batch_start : batch_start + batch_size]
                partial_snapshots.extend(
                    await asyncio.gather(
                        *[
                            workflow.execute_activity(
                                extract_order_snapshot_chunk,
                                args=[chunk],
                                start_to_close_timeout=timedelta(minutes=3),
                            )
                            for chunk in batch
                        ]
                    )
                )
                first_section = batch_start + 1
                last_section = batch_start + len(batch)
                await workflow.execute_activity(
                    set_processing_stage,
                    args=[run["processing_run_id"], f"sections_{first_section}_{last_section}_extracted", database_path],
                    start_to_close_timeout=timedelta(seconds=30),
                )
            snapshot = await workflow.execute_activity(
                stitch_order_snapshot,
        validate_order_snapshot,
                args=[partial_snapshots],
                start_to_close_timeout=timedelta(minutes=1),
            )
            await workflow.execute_activity(
                set_processing_stage,
                args=[run["processing_run_id"], "snapshot_stitched", database_path],
                start_to_close_timeout=timedelta(seconds=30),
            )
            snapshot = await workflow.execute_activity(
                validate_order_snapshot,
                args=[snapshot],
                start_to_close_timeout=timedelta(seconds=30),
            )
            await workflow.execute_activity(
                set_processing_stage,
                args=[run["processing_run_id"], "snapshot_validated", database_path],
                start_to_close_timeout=timedelta(seconds=30),
            )
            return await workflow.execute_activity(
                persist_supplier_version,
                args=[email_id, run["processing_run_id"], snapshot, database_path],
                start_to_close_timeout=timedelta(minutes=1),
            )
        except Exception as error:
            await workflow.execute_activity(
                mark_processing_failed,
                args=[run["processing_run_id"], str(error), database_path],
                start_to_close_timeout=timedelta(seconds=30),
            )
            raise


@workflow.defn
class OrderQuestionWorkflow:
    @workflow.run
    async def run(self, message_id: int, database_path: str) -> dict[str, int]:
        return await workflow.execute_activity(answer_order_question, args=[message_id, database_path], start_to_close_timeout=timedelta(minutes=2))


@workflow.defn
class OrderChangeRequestWorkflow:
    @workflow.run
    async def run(self, message_id: int, database_path: str) -> dict[str, int]:
        return await workflow.execute_activity(propose_order_change, args=[message_id, database_path], start_to_close_timeout=timedelta(minutes=2))


@workflow.defn
class ChatRoutingWorkflow:
    @workflow.run
    async def run(self, message_id: int, database_path: str) -> dict:
        decision = await workflow.execute_activity(classify_chat_intent, args=[message_id, database_path], start_to_close_timeout=timedelta(seconds=30))
        if decision["intent"] == "question":
            result = await workflow.execute_child_workflow(OrderQuestionWorkflow.run, args=[message_id, database_path], id=f"{workflow.info().workflow_id}-question")
        elif decision["intent"] == "change_request":
            result = await workflow.execute_child_workflow(OrderChangeRequestWorkflow.run, args=[message_id, database_path], id=f"{workflow.info().workflow_id}-change")
        else:
            result = await workflow.execute_activity(respond_to_unsupported_request, args=[message_id, database_path], start_to_close_timeout=timedelta(seconds=30))
        return {"intent": decision["intent"], "confidence": decision["confidence"], **result}