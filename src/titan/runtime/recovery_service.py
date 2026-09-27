from dataclasses import dataclass
from titan.config import settings
from titan.integrations.temporal.client import get_temporal_client
from sqlalchemy import select

from titan.persistence.models import (
    EventModel,
    ProjectModel,
    ProjectStateModel,
    WorkflowModel,
)
from titan.runtime.replanner import ReplanDecision
from titan.runtime.replanning_service import replan_failed_workflow
from titan.runtime.recovery_strategy import RecoveryStrategy
from titan.runtime.service import AgentRuntime, get_agent_runtime
from titan.workflows.runtime import TitanWorkflow
from titan.workflows.service import build_workflow_input


@dataclass(frozen=True, slots=True)
class RecoveryStartResult:
    replacement_workflow_id: UUID
    replacement_task_graph_id: UUID
    recovery_attempt: int
    strategy: str
    decision: ReplanDecision
    preserved_task_count: int


async def start_recovery_workflow(
    session,
    *,
    project: ProjectModel,
    workflow: WorkflowModel,
    run_id: str,
    error_message: str,
    recovery_attempt: int,
    recovery_root_workflow_id: str,
    failure_category: str,
    strategy: RecoveryStrategy,
    runtime: AgentRuntime | None = None,
) -> RecoveryStartResult:
    if recovery_attempt < 1:
        raise ValueError("Recovery attempt must be at least 1")

    runtime = runtime or get_agent_runtime()
    allow_reassignment = strategy is RecoveryStrategy.REPLAN_REASSIGN

    graph, new_tasks, decision = await replan_failed_workflow(
        session,
        project=project,
        workflow=workflow,
        capability_registry=runtime.capabilities,
        contracts=runtime.contracts.all(),
        allow_reassignment=allow_reassignment,
        recovery_strategy=strategy.value,
    )

    replacement = WorkflowModel(
        project_id=project.id,
        task_graph_id=graph.id,
        name=f"Recovery {recovery_attempt} for {workflow.name}",
        workflow_type="RECOVERY",
        status="STARTING",
    )
    session.add(replacement)
    await session.flush()

    for task in new_tasks:
        if task.workflow_id is not None:
            raise ValueError(
                f"Recovery task {task.id} is already assigned to a workflow"
            )
        task.workflow_id = replacement.id

    graph.status = "RUNNING"
    temporal_workflow_id = (
        f"titan-recovery-{workflow.id}-{recovery_attempt}-{replacement.id}"
    )
    replacement.temporal_workflow_id = temporal_workflow_id

    precompleted = tuple(
        str(task.id)
        for task in new_tasks
        if task.status == "COMPLETED"
    )

    request = await build_workflow_input(
        session,
        project=project,
        workflow=replacement,
        tasks=list(new_tasks),
        runtime=runtime,
        precompleted_task_ids=precompleted,
        recovery_attempt=recovery_attempt,
        recovery_root_workflow_id=recovery_root_workflow_id,
    )

    temporal_client = await get_temporal_client()
    await temporal_client.start_workflow(
        TitanWorkflow.run,
        request,
        id=temporal_workflow_id,
        task_queue=settings.temporal_task_queue,
    )

    session.add(
        EventModel(
            project_id=project.id,
            type="WorkflowRecoveryStarted",
            actor_type="SYSTEM",
            aggregate_type="WORKFLOW",
            aggregate_id=replacement.id,
            payload={
                "source_workflow_id": str(workflow.id),
                "source_run_id": run_id,
                "recovery_attempt": recovery_attempt,
                "recovery_root_workflow_id": recovery_root_workflow_id,
                "failure_category": failure_category,
                "strategy": strategy.value,
                "task_graph_id": str(graph.id),
                "failed_task_ids": list(decision.failed_task_ids),
                "impacted_task_ids": list(decision.impacted_task_ids),
                "reassigned_task_count": len(decision.reassignments),
                "precompleted_task_count": len(precompleted),
                "error_message": error_message,
            },
        )
    )
    session.add(
        EventModel(
            project_id=project.id,
            type="RecoveryStarted",
            actor_type="SYSTEM",
            aggregate_type="WORKFLOW",
            aggregate_id=workflow.id,
            payload={
                "replacement_workflow_id": str(replacement.id),
                "replacement_task_graph_id": str(graph.id),
                "recovery_attempt": recovery_attempt,
                "failure_category": failure_category,
                "strategy": strategy.value,
                "precompleted_task_count": len(precompleted),
            },
        )
    )

    state = await session.scalar(
        select(ProjectStateModel).where(
            ProjectStateModel.project_id == project.id
        )
    )
    if state is not None:
        state.status = "RUNNING"
        state.phase = "RECOVERY_EXECUTION"
        state.version += 1

    return RecoveryStartResult(
        replacement_workflow_id=replacement.id,
        replacement_task_graph_id=graph.id,
        recovery_attempt=recovery_attempt,
        strategy=strategy.value,
        decision=decision,
        preserved_task_count=len(precompleted),
    )
