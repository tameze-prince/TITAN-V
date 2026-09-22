from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from titan.workflows.contracts import WorkflowInput
from titan.workflows.runtime import TitanWorkflow


@activity.defn(name="mark_workflow_started")
async def fake_mark_workflow_started(
    workflow_id,
    temporal_workflow_id: str,
    temporal_run_id: str,
):
    return workflow_id


@activity.defn(name="orchestrate_task")
async def fake_orchestrate_task(workflow_id, task_id, run_id) -> bool:
    return True


@activity.defn(name="mark_workflow_completed")
async def fake_mark_workflow_completed(workflow_id, run_id, completed_task_ids) -> None:
    return None


@activity.defn(name="mark_workflow_failed")
async def fake_mark_workflow_failed(workflow_id, run_id, error_message: str) -> None:
    return None


@pytest.mark.asyncio
async def test_titan_workflow_orchestrates_tasks() -> None:
    async with await WorkflowEnvironment.start_time_skipping() as env, Worker(
        env.client,
        task_queue="titan-test",
        workflows=[TitanWorkflow],
        activities=[
            fake_mark_workflow_started,
            fake_orchestrate_task,
            fake_mark_workflow_completed,
            fake_mark_workflow_failed,
        ],
    ):
            request = WorkflowInput(
                workflow_id=uuid4(),
                project_id=uuid4(),
                task_ids=(uuid4(), uuid4()),
            )
            result = await env.client.execute_workflow(
                TitanWorkflow.run,
                request,
                id="titan-test-workflow",
                task_queue="titan-test",
            )

    assert result.status == "COMPLETED"
    assert result.completed_task_ids == request.task_ids
