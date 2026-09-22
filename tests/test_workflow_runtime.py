import asyncio
import os
from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from titan.workflows.contracts import WorkflowInput
from titan.workflows.runtime import TitanWorkflow


@activity.defn(name="mark_workflow_started")
async def fake_mark_workflow_started(
    workflow_id: str,
    temporal_workflow_id: str,
    temporal_run_id: str,
) -> str:
    return workflow_id


@activity.defn(name="orchestrate_task")
async def fake_orchestrate_task(workflow_id: str, task_id: str, run_id: str) -> bool:
    return True


@activity.defn(name="mark_workflow_completed")
async def fake_mark_workflow_completed(
    workflow_id: str,
    run_id: str,
    completed_task_ids: tuple[str, ...],
) -> None:
    return None


@activity.defn(name="mark_workflow_failed")
async def fake_mark_workflow_failed(
    workflow_id: str,
    run_id: str,
    error_message: str,
) -> None:
    return None


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("TITAN_RUN_TEMPORAL_INTEGRATION") != "1",
    reason="Temporal integration tests require TITAN_RUN_TEMPORAL_INTEGRATION=1",
)
async def test_titan_workflow_orchestrates_tasks() -> None:
    target = os.getenv("TITAN_TEMPORAL_TARGET", "localhost:7233")
    namespace = os.getenv("TITAN_TEMPORAL_NAMESPACE", "default")
    task_queue = os.getenv("TITAN_TEMPORAL_TASK_QUEUE", "titan-ci")

    client = await Client.connect(target, namespace=namespace)

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[TitanWorkflow],
        activities=[
            fake_mark_workflow_started,
            fake_orchestrate_task,
            fake_mark_workflow_completed,
            fake_mark_workflow_failed,
        ],
    ):
        request = WorkflowInput(
            workflow_id=str(uuid4()),
            project_id=str(uuid4()),
            task_ids=(str(uuid4()), str(uuid4())),
        )
        result = await asyncio.wait_for(
            client.execute_workflow(
                TitanWorkflow.run,
                request,
                id=f"titan-test-workflow-{uuid4()}",
                task_queue=task_queue,
            ),
            timeout=30,
        )

    assert result.status == "COMPLETED"
    assert result.completed_task_ids == request.task_ids
