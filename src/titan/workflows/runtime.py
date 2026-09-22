from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from titan.workflows.contracts import WorkflowInput, WorkflowResult

with workflow.unsafe.imports_passed_through():
    from titan.workflows.activities import (
        mark_workflow_completed,
        mark_workflow_failed,
        mark_workflow_started,
        orchestrate_task,
    )


@workflow.defn
RETRY_POLICY = RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3)


@workflow.defn
class TitanWorkflow:
    @workflow.run
    async def run(self, request: WorkflowInput) -> WorkflowResult:
        temporal_workflow_id = workflow.info().workflow_id
        temporal_run_id = workflow.info().run_id

        run_id: str = await workflow.execute_activity(
            mark_workflow_started,
            request.workflow_id,
            temporal_workflow_id,
            temporal_run_id,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY_POLICY,
        )

        completed_task_ids: list[str] = []

        try:
            for task_id in request.task_ids:
                await workflow.execute_activity(
                    orchestrate_task,
                    request.workflow_id,
                    task_id,
                    run_id,
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=RETRY_POLICY,
                )
                completed_task_ids.append(task_id)

            await workflow.execute_activity(
                mark_workflow_completed,
                request.workflow_id,
                run_id,
                tuple(completed_task_ids),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RETRY_POLICY,
            )

            return WorkflowResult(
                workflow_id=request.workflow_id,
                status="COMPLETED",
                completed_task_ids=tuple(completed_task_ids),
                run_id=run_id,
            )
        except Exception as exc:
            await workflow.execute_activity(
                mark_workflow_failed,
                request.workflow_id,
                run_id,
                str(exc),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RETRY_POLICY,
            )
            raise
