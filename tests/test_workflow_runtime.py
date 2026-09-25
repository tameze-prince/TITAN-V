import asyncio
import os
from uuid import uuid4

import pytest
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from titan.workflows.contracts import WorkflowInput, WorkflowTaskProfile
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
        task_a = str(uuid4())
        task_b = str(uuid4())
        task_c = str(uuid4())
        task_d = str(uuid4())
        request = WorkflowInput(
            workflow_id=str(uuid4()),
            project_id=str(uuid4()),
            task_ids=(task_a, task_b, task_c, task_d),
            dependencies=((task_c, (task_a, task_b)),),
            task_agents=(
                (task_a, "general-executor"),
                (task_b, "general-executor"),
                (task_c, "general-executor"),
                (task_d, "engineering-executor"),
            ),
            agent_capacities=(
                ("general-executor", 1),
                ("engineering-executor", 1),
            ),
            task_profiles=(
                WorkflowTaskProfile(
                    task_id=task_a,
                    risk_level="R2",
                    minimum_quality_tier=2,
                    estimated_cost=1.0,
                    priority=5,
                ),
                WorkflowTaskProfile(
                    task_id=task_b,
                    risk_level="R1",
                    minimum_quality_tier=1,
                    estimated_cost=1.0,
                ),
                WorkflowTaskProfile(
                    task_id=task_c,
                    risk_level="R3",
                    minimum_quality_tier=2,
                    estimated_cost=2.0,
                ),
                WorkflowTaskProfile(
                    task_id=task_d,
                    risk_level="R1",
                    minimum_quality_tier=1,
                    estimated_cost=0.5,
                ),
            ),
            max_project_cost=10.0,
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
    assert result.completed_task_ids == (
        task_a,
        task_d,
        task_b,
        task_c,
    )
    assert result.execution_waves == (
        (task_a, task_d),
        (task_b,),
        (task_c,),
    )
    assert result.estimated_schedule_cost == 4.5
