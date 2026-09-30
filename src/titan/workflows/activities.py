from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from temporalio import activity

from titan.persistence.database import SessionFactory
from titan.persistence.models import (
    ArtifactModel,
    EvaluationModel,
    EventModel,
    ProjectModel,
    ProjectStateModel,
    RepairAttemptModel,
    RunModel,
    TaskGraphModel,
    TaskModel,
    WorkflowModel,
    task_dependencies,
)
from titan.runtime.contracts import AgentTaskContext
from titan.runtime.evaluation_service import EvaluationCheck, EvaluationEngine
from titan.runtime.governance import GovernanceEngine
from titan.runtime.governance_audit import record_governance_decision
from titan.runtime.memory import MemoryStore
from titan.runtime.repair import AgentEvaluationFailure
from titan.runtime.recovery_strategy import (
    RecoveryStrategySelector,
    classify_failure,
    observations_from_events,
)
from titan.runtime.service import get_agent_runtime


async def _run_recovery_cost(
    session,
    *,
    project_id: UUID,
    run_id: UUID,
) -> float:
    events = list(
        await session.scalars(
            select(EventModel)
            .where(
                EventModel.project_id == project_id,
                EventModel.type == "ModelUsageRecorded",
            )
            .order_by(EventModel.occurred_at.desc())
            .limit(5000)
        )
    )
    total = 0.0
    run_id_text = str(run_id)
    for event in events:
        payload = event.payload or {}
        if payload.get("run_id") != run_id_text:
            continue
        usage = payload.get("usage") or {}
        try:
            total += float(usage.get("estimated_cost") or 0.0)
        except (TypeError, ValueError):
            continue
    return round(total, 8)


@activity.defn
async def mark_workflow_started(
    workflow_id: str,
    temporal_workflow_id: str,
    temporal_run_id: str,
) -> str:
    workflow_uuid = UUID(workflow_id)

    async with SessionFactory() as session:
        workflow = await session.scalar(
            select(WorkflowModel).where(WorkflowModel.id == workflow_uuid)
        )
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found")

        existing_run = await session.scalar(
            select(RunModel).where(RunModel.temporal_run_id == temporal_run_id)
        )
        if existing_run is not None:
            return str(existing_run.id)

        run = RunModel(
            workflow_id=workflow_uuid,
            temporal_workflow_id=temporal_workflow_id,
            temporal_run_id=temporal_run_id,
        )
        workflow.status = "RUNNING"

        state = await session.scalar(
            select(ProjectStateModel).where(
                ProjectStateModel.project_id == workflow.project_id
            )
        )
        if state is not None:
            state.status = "RUNNING"
            state.phase = "EXECUTION"
            state.version += 1
        workflow.temporal_workflow_id = temporal_workflow_id
        workflow.temporal_run_id = temporal_run_id
        workflow.started_at = datetime.now(UTC)

        session.add(run)
        session.add(
            EventModel(
                project_id=workflow.project_id,
                type="WorkflowStarted",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={
                    "temporal_workflow_id": temporal_workflow_id,
                    "temporal_run_id": temporal_run_id,
                },
            )
        )

        await session.commit()
        return str(run.id)


@activity.defn
async def orchestrate_task(
    workflow_id: str,
    task_id: str,
    run_id: str,
) -> bool:
    workflow_uuid = UUID(workflow_id)
    task_uuid = UUID(task_id)

    async with SessionFactory() as session:
        task = await session.scalar(
            select(TaskModel)
            .options(selectinload(TaskModel.owner_agent))
            .where(TaskModel.id == task_uuid)
        )
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        if task.workflow_id != workflow_uuid:
            raise ValueError(f"Task {task_id} does not belong to workflow {workflow_id}")

        if task.status == "COMPLETED":
            return True

        dependency_ids = list(
            (
                await session.execute(
                    select(task_dependencies.c.depends_on_task_id).where(
                        task_dependencies.c.task_id == task.id
                    )
                )
            ).scalars()
        )
        if dependency_ids:
            incomplete_dependency = await session.scalar(
                select(TaskModel)
                .where(
                    TaskModel.id.in_(dependency_ids),
                    TaskModel.status != "COMPLETED",
                )
                .limit(1)
            )
            if incomplete_dependency is not None:
                task.status = "BLOCKED"
                session.add(
                    EventModel(
                        project_id=task.project_id,
                        type="TaskBlocked",
                        actor_type="SYSTEM",
                        aggregate_type="TASK",
                        aggregate_id=task.id,
                        payload={
                            "run_id": run_id,
                            "dependency_task_id": str(incomplete_dependency.id),
                            "dependency_status": incomplete_dependency.status,
                        },
                    )
                )
                await session.commit()
                raise RuntimeError(
                    f"Task {task.id} has an incomplete dependency "
                    f"{incomplete_dependency.id}"
                )

        task.status = "RUNNING"
        agent_name = (
            task.owner_agent.name
            if task.owner_agent is not None
            else "general-executor"
        )
        session.add(
            EventModel(
                project_id=task.project_id,
                type="TaskStarted",
                actor_type="SYSTEM",
                aggregate_type="TASK",
                aggregate_id=task.id,
                payload={
                    "run_id": run_id,
                    "execution_mode": "agent-runtime",
                    "agent_name": agent_name,
                },
            )
        )
        await session.flush()

        runtime = get_agent_runtime()
        memory_store = MemoryStore()
        evaluation_engine = EvaluationEngine()
        latest_repair = await session.scalar(
            select(RepairAttemptModel)
            .join(EvaluationModel, RepairAttemptModel.evaluation_id == EvaluationModel.id)
            .where(
                EvaluationModel.task_id == task.id,
                EvaluationModel.run_id == UUID(run_id),
            )
            .order_by(RepairAttemptModel.created_at.desc())
        )
        repair_inputs = {}
        if latest_repair is not None:
            repair_inputs = {
                "repair_diagnosis": latest_repair.diagnosis,
                "repair_context": latest_repair.corrective_action,
                "repair_attempt": latest_repair.attempt,
            }

        context = AgentTaskContext(
            task_id=task_id,
            run_id=run_id,
            project_id=str(task.project_id),
            title=task.title,
            objective=task.objective,
            risk_level=task.risk_level,
            inputs=repair_inputs,
        )

        try:
            execution = await runtime.execute(context, agent_name=agent_name)
            artifact_content = execution.model_dump_json()

            evaluation_payload = execution.evaluation
            checks_payload = evaluation_payload.get("checks", {})
            evaluation_result = evaluation_engine.evaluate(
                checks=tuple(
                    EvaluationCheck(
                        name=name,
                        passed=bool(passed),
                        evidence=evaluation_payload.get("message", ""),
                    )
                    for name, passed in checks_payload.items()
                )
                or (
                    EvaluationCheck(
                        name="baseline",
                        passed=bool(evaluation_payload.get("passed", False)),
                        evidence=evaluation_payload.get("message", ""),
                    ),
                )
            )

            await memory_store.remember(
                session,
                project_id=task.project_id,
                task_id=task.id,
                kind="EXECUTION_SUMMARY",
                content=execution.output.summary,
                importance=70,
                source_type="TASK_RUN",
                source_id=task.id,
                metadata={
                    "agent_name": execution.agent_name,
                    "provider": execution.provider,
                    "model": execution.model,
                    "run_id": run_id,
                },
            )

            tool_results = execution.output.result.get("tool_results", [])
            if tool_results:
                tool_memory = str(tool_results)[:12_000]
                await memory_store.remember(
                    session,
                    project_id=task.project_id,
                    task_id=task.id,
                    kind="TOOL_EVIDENCE",
                    content=tool_memory,
                    importance=60,
                    source_type="TASK_RUN",
                    source_id=task.id,
                    metadata={"run_id": run_id},
                )

            await evaluation_engine.persist(
                session,
                project_id=task.project_id,
                task_id=task.id,
                run_id=UUID(run_id),
                result=evaluation_result,
            )

            artifact = ArtifactModel(
                project_id=task.project_id,
                type="AGENT_RESULT",
                title=f"{task.title} — agent result",
                status="FINAL",
                media_type="application/json",
                content_ref=artifact_content,
                checksum=sha256(artifact_content.encode("utf-8")).hexdigest(),
            )
            session.add(artifact)

            task.status = "COMPLETED"
            session.add(
                EventModel(
                    project_id=task.project_id,
                    type="AgentEvaluated",
                    actor_type="SYSTEM",
                    aggregate_type="TASK",
                    aggregate_id=task.id,
                    payload=execution.evaluation,
                )
            )
            session.add(
                EventModel(
                    project_id=task.project_id,
                    type="ModelUsageRecorded",
                    actor_type="SYSTEM",
                    aggregate_type="TASK",
                    aggregate_id=task.id,
                    payload={
                        "run_id": run_id,
                        "provider": execution.provider,
                        "model": execution.model,
                        "duration_ms": execution.duration_ms,
                        "usage": execution.usage,
                    },
                )
            )
            session.add(
                EventModel(
                    project_id=task.project_id,
                    type="ArtifactCreated",
                    actor_type="SYSTEM",
                    aggregate_type="ARTIFACT",
                    aggregate_id=artifact.id,
                    payload={
                        "task_id": task_id,
                        "artifact_type": artifact.type,
                        "checksum": artifact.checksum,
                    },
                )
            )
            session.add(
                EventModel(
                    project_id=task.project_id,
                    type="TaskCompleted",
                    actor_type="SYSTEM",
                    aggregate_type="TASK",
                    aggregate_id=task.id,
                    payload={
                        "run_id": run_id,
                        "agent_name": execution.agent_name,
                        "provider": execution.provider,
                        "model": execution.model,
                        "duration_ms": execution.duration_ms,
                    },
                )
            )
            await session.commit()
            return True
        except AgentEvaluationFailure as exc:
            evaluation = await evaluation_engine.persist(
                session,
                project_id=task.project_id,
                task_id=task.id,
                run_id=UUID(run_id),
                result=evaluation_engine.evaluate(
                    checks=tuple(
                        EvaluationCheck(
                            name=name,
                            passed=passed,
                            evidence=exc.evaluation.message,
                        )
                        for name, passed in exc.evaluation.checks.items()
                    ),
                    evaluator_type="AGENT_RUNTIME",
                ),
            )
            await evaluation_engine.plan_repair(
                session,
                evaluation_id=evaluation.id,
                task_id=task.id,
                attempt=exc.plan.attempt,
                diagnosis=exc.plan.diagnosis,
                corrective_action=exc.plan.corrective_action,
            )
            await memory_store.remember(
                session,
                project_id=task.project_id,
                task_id=task.id,
                kind="REPAIR_DIAGNOSIS",
                content=exc.plan.diagnosis,
                importance=85,
                source_type="EVALUATION",
                source_id=evaluation.id,
                metadata={"run_id": run_id, "attempt": exc.plan.attempt},
            )
            final_attempt = activity.info().attempt >= 3
            task.status = "FAILED" if final_attempt else "REPAIRING"
            session.add(
                EventModel(
                    project_id=task.project_id,
                    type="TaskRepairPlanned" if not final_attempt else "TaskFailed",
                    actor_type="SYSTEM",
                    aggregate_type="TASK",
                    aggregate_id=task.id,
                    payload={
                        "run_id": run_id,
                        "attempt": exc.plan.attempt,
                        "diagnosis": exc.plan.diagnosis,
                        "corrective_action": exc.plan.corrective_action,
                        "final_attempt": final_attempt,
                    },
                )
            )
            await session.commit()
            raise
        except Exception as exc:
            final_attempt = activity.info().attempt >= 3
            task.status = "FAILED" if final_attempt else "RETRYING"
            session.add(
                EventModel(
                    project_id=task.project_id,
                    type="TaskFailed" if final_attempt else "TaskRetrying",
                    actor_type="SYSTEM",
                    aggregate_type="TASK",
                    aggregate_id=task.id,
                    payload={
                        "run_id": run_id,
                        "attempt": activity.info().attempt,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "final_attempt": final_attempt,
                    },
                )
            )
            await session.commit()
            raise


@activity.defn
async def mark_task_waiting_for_approval(
    workflow_id: str,
    task_id: str,
    run_id: str,
) -> str:
    workflow_uuid = UUID(workflow_id)
    task_uuid = UUID(task_id)

    async with SessionFactory() as session:
        task = await session.scalar(
            select(TaskModel)
            .where(
                TaskModel.id == task_uuid,
                TaskModel.workflow_id == workflow_uuid,
            )
            .with_for_update()
        )
        if task is None:
            raise ValueError(f"Approval task {task_id} not found")

        if task.status == "APPROVED":
            return "APPROVED"
        if task.status == "COMPLETED":
            return "COMPLETED"
        if task.status == "REJECTED":
            return "REJECTED"
        if task.status == "WAITING_APPROVAL":
            return "WAITING_APPROVAL"

        task.status = "WAITING_APPROVAL"
        session.add(
            EventModel(
                project_id=task.project_id,
                type="TaskApprovalRequested",
                actor_type="SYSTEM",
                aggregate_type="TASK",
                aggregate_id=task.id,
                payload={
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "approval_requirement": task.approval_requirement,
                    "reason": "Task requires human approval before execution",
                },
            )
        )
        state = await session.scalar(
            select(ProjectStateModel).where(
                ProjectStateModel.project_id == task.project_id
            )
        )
        if state is not None:
            state.status = "WAITING_HUMAN"
            state.phase = "WAITING_APPROVAL"
            state.version += 1

        await session.commit()
        return "WAITING_APPROVAL"


@activity.defn
async def mark_task_approval_rejected(
    workflow_id: str,
    task_id: str,
    reason: str,
) -> None:
    workflow_uuid = UUID(workflow_id)
    task_uuid = UUID(task_id)

    async with SessionFactory() as session:
        task = await session.scalar(
            select(TaskModel).where(
                TaskModel.id == task_uuid,
                TaskModel.workflow_id == workflow_uuid,
            )
        )
        if task is None:
            raise ValueError(f"Approval task {task_id} not found")

        task.status = "REJECTED"
        session.add(
            EventModel(
                project_id=task.project_id,
                type="TaskApprovalRejected",
                actor_type="OPERATOR",
                aggregate_type="TASK",
                aggregate_id=task.id,
                payload={
                    "reason": reason or "Task approval rejected by operator",
                },
            )
        )
        await session.commit()


@activity.defn
async def mark_workflow_approval_expired(
    workflow_id: str,
    run_id: str,
    task_id: str,
    timeout_seconds: int,
) -> str:
    workflow_uuid = UUID(workflow_id)
    run_uuid = UUID(run_id)
    task_uuid = UUID(task_id)

    async with SessionFactory() as session:
        workflow = await session.scalar(
            select(WorkflowModel).where(WorkflowModel.id == workflow_uuid)
        )
        run = await session.scalar(select(RunModel).where(RunModel.id == run_uuid))
        task = await session.scalar(
            select(TaskModel).where(
                TaskModel.id == task_uuid,
                TaskModel.workflow_id == workflow_uuid,
            )
        )
        if workflow is None or run is None or task is None:
            raise ValueError("Workflow approval timeout state not found")

        now = datetime.now(UTC)
        if task.status in {"APPROVED", "COMPLETED", "REJECTED", "EXPIRED"}:
            return task.status

        task.status = "EXPIRED"
        workflow.status = "EXPIRED"
        workflow.completed_at = now
        run.status = "EXPIRED"
        run.completed_at = now

        state = await session.scalar(
            select(ProjectStateModel).where(
                ProjectStateModel.project_id == workflow.project_id
            )
        )
        if state is not None:
            state.status = "EXPIRED"
            state.phase = "HUMAN_APPROVAL_TIMEOUT"
            state.version += 1

        if workflow.task_graph_id is not None:
            graph = await session.scalar(
                select(TaskGraphModel).where(TaskGraphModel.id == workflow.task_graph_id)
            )
            if graph is not None:
                graph.status = "EXPIRED"

        session.add(
            EventModel(
                project_id=workflow.project_id,
                type="TaskApprovalExpired",
                actor_type="SYSTEM",
                aggregate_type="TASK",
                aggregate_id=task.id,
                payload={
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "timeout_seconds": timeout_seconds,
                    "reason": "Human approval window expired",
                },
            )
        )
        session.add(
            EventModel(
                project_id=workflow.project_id,
                type="WorkflowApprovalExpired",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={
                    "run_id": run_id,
                    "task_id": task_id,
                    "timeout_seconds": timeout_seconds,
                    "reason": "Human approval window expired",
                },
            )
        )
        await session.commit()
        return "EXPIRED"


@activity.defn
async def mark_workflow_rejected(
    workflow_id: str,
    run_id: str,
    task_id: str,
    reason: str,
    operator_subject: str = "unknown",
    operator_role: str = "unknown",
) -> None:
    workflow_uuid = UUID(workflow_id)
    run_uuid = UUID(run_id)

    async with SessionFactory() as session:
        workflow = await session.scalar(
            select(WorkflowModel).where(WorkflowModel.id == workflow_uuid)
        )
        run = await session.scalar(
            select(RunModel).where(RunModel.id == run_uuid)
        )
        if workflow is None or run is None:
            raise ValueError("Workflow run state not found")

        now = datetime.now(UTC)
        workflow.status = "REJECTED"
        workflow.completed_at = now
        run.status = "REJECTED"
        run.completed_at = now

        state = await session.scalar(
            select(ProjectStateModel).where(
                ProjectStateModel.project_id == workflow.project_id
            )
        )
        if state is not None:
            state.status = "REJECTED"
            state.phase = "HUMAN_REJECTED"
            state.version += 1

        if workflow.task_graph_id is not None:
            graph = await session.scalar(
                select(TaskGraphModel).where(
                    TaskGraphModel.id == workflow.task_graph_id
                )
            )
            if graph is not None:
                graph.status = "REJECTED"

        session.add(
            EventModel(
                project_id=workflow.project_id,
                type="WorkflowRejected",
                actor_type="OPERATOR",
                actor_subject=operator_subject,
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={
                    "run_id": run_id,
                    "task_id": task_id,
                    "reason": reason or "Workflow execution rejected by operator",
                    "operator_subject": operator_subject,
                    "operator_role": operator_role,
                },
            )
        )
        await session.commit()


@activity.defn
async def mark_workflow_completed(
    workflow_id: str,
    run_id: str,
    completed_task_ids: tuple[str, ...],
) -> None:
    workflow_uuid = UUID(workflow_id)
    run_uuid = UUID(run_id)

    async with SessionFactory() as session:
        workflow = await session.scalar(
            select(WorkflowModel).where(WorkflowModel.id == workflow_uuid)
        )
        run = await session.scalar(select(RunModel).where(RunModel.id == run_uuid))
        if workflow is None or run is None:
            raise ValueError("Workflow run state not found")

        now = datetime.now(UTC)
        workflow.status = "COMPLETED"
        workflow.completed_at = now
        run.status = "SUCCEEDED"
        run.completed_at = now
        run.metrics = {"completed_tasks": len(completed_task_ids)}

        if workflow.task_graph_id is not None:
            state = await session.scalar(
                select(ProjectStateModel).where(
                    ProjectStateModel.project_id == workflow.project_id
                )
            )
            if state is not None:
                state.status = "COMPLETED"
                state.phase = "COMPLETED"
                state.version += 1
            task_graph = await session.scalar(
                select(TaskGraphModel).where(
                    TaskGraphModel.id == workflow.task_graph_id
                )
            )
            if task_graph is not None:
                task_graph.status = "COMPLETED"

        recovery_started = await session.scalar(
            select(EventModel)
            .where(
                EventModel.aggregate_type == "WORKFLOW",
                EventModel.aggregate_id == workflow.id,
                EventModel.type == "WorkflowRecoveryStarted",
            )
            .order_by(EventModel.occurred_at.desc())
            .limit(1)
        )

        session.add(
            EventModel(
                project_id=workflow.project_id,
                type="WorkflowCompleted",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={"completed_task_count": len(completed_task_ids)},
            )
        )

        if recovery_started is not None:
            recovery_payload = recovery_started.payload or {}
            precompleted_count = int(recovery_payload.get("precompleted_task_count", 0))
            recovery_attempt = int(recovery_payload.get("recovery_attempt", 0))
            source_workflow_id = recovery_payload.get("source_workflow_id")
            recovery_root_workflow_id = recovery_payload.get("recovery_root_workflow_id")
            reexecuted_count = max(0, len(completed_task_ids) - precompleted_count)
            actual_cost = await _run_recovery_cost(
                session,
                project_id=workflow.project_id,
                run_id=run_uuid,
            )
            duration_ms = (
                max(
                    0,
                    int(
                        (
                            now - workflow.started_at
                        ).total_seconds() * 1000
                    ),
                )
                if workflow.started_at is not None
                else 0
            )
            session.add(
                EventModel(
                    project_id=workflow.project_id,
                    type="RecoveryResolved",
                    actor_type="SYSTEM",
                    aggregate_type="WORKFLOW",
                    aggregate_id=workflow.id,
                    payload={
                        "source_workflow_id": source_workflow_id,
                        "recovery_attempt": recovery_attempt,
                        "recovery_root_workflow_id": recovery_root_workflow_id,
                        "failure_category": recovery_payload.get("failure_category"),
                        "strategy": recovery_payload.get("strategy"),
                        "actual_cost": actual_cost,
                        "duration_ms": duration_ms,
                        "completed_task_count": len(completed_task_ids),
                        "preserved_task_count": precompleted_count,
                        "reexecuted_task_count": reexecuted_count,
                    },
                )
            )
            await MemoryStore().remember(
                session,
                project_id=workflow.project_id,
                task_id=None,
                kind="RECOVERY_OUTCOME",
                content=(
                    f"Recovery attempt {recovery_attempt} resolved workflow "
                    f"{source_workflow_id} through replacement workflow {workflow.id}."
                ),
                importance=96,
                source_type="RECOVERY",
                source_id=workflow.id,
                metadata={
                    "source_workflow_id": source_workflow_id,
                    "recovery_attempt": recovery_attempt,
                    "failure_category": recovery_payload.get("failure_category"),
                    "strategy": recovery_payload.get("strategy"),
                    "actual_cost": actual_cost,
                    "duration_ms": duration_ms,
                    "preserved_task_count": precompleted_count,
                    "reexecuted_task_count": reexecuted_count,
                },
            )

        await session.commit()


@activity.defn
async def mark_workflow_failed(
    workflow_id: str,
    run_id: str,
    error_message: str,
) -> None:
    workflow_uuid = UUID(workflow_id)
    run_uuid = UUID(run_id)

    async with SessionFactory() as session:
        workflow = await session.scalar(
            select(WorkflowModel).where(WorkflowModel.id == workflow_uuid)
        )
        run = await session.scalar(select(RunModel).where(RunModel.id == run_uuid))
        if workflow is None or run is None:
            raise ValueError("Workflow run state not found")

        now = datetime.now(UTC)
        workflow.status = "FAILED"
        workflow.completed_at = now
        run.status = "FAILED"
        run.completed_at = now
        run.error_code = "WORKFLOW_FAILED"
        run.error_message = error_message

        if workflow.task_graph_id is not None:
            state = await session.scalar(
                select(ProjectStateModel).where(
                    ProjectStateModel.project_id == workflow.project_id
                )
            )
            if state is not None:
                state.status = "FAILED"
                state.phase = "EXECUTION_FAILED"
                state.version += 1
            task_graph = await session.scalar(
                select(TaskGraphModel).where(
                    TaskGraphModel.id == workflow.task_graph_id
                )
            )
            if task_graph is not None:
                task_graph.status = "FAILED"

        recovery_started = await session.scalar(
            select(EventModel)
            .where(
                EventModel.aggregate_type == "WORKFLOW",
                EventModel.aggregate_id == workflow.id,
                EventModel.type == "WorkflowRecoveryStarted",
            )
            .order_by(EventModel.occurred_at.desc())
            .limit(1)
        )

        session.add(
            EventModel(
                project_id=workflow.project_id,
                type="WorkflowFailed",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={"error_message": error_message},
            )
        )

        if recovery_started is not None:
            recovery_payload = recovery_started.payload or {}
            actual_cost = await _run_recovery_cost(
                session,
                project_id=workflow.project_id,
                run_id=run_uuid,
            )
            duration_ms = (
                max(
                    0,
                    int(
                        (
                            now - workflow.started_at
                        ).total_seconds() * 1000
                    ),
                )
                if workflow.started_at is not None
                else 0
            )
            session.add(
                EventModel(
                    project_id=workflow.project_id,
                    type="RecoveryRepeatedFailure",
                    actor_type="SYSTEM",
                    aggregate_type="WORKFLOW",
                    aggregate_id=workflow.id,
                    payload={
                        "source_workflow_id": recovery_payload.get("source_workflow_id"),
                        "recovery_attempt": recovery_payload.get("recovery_attempt", 0),
                        "recovery_root_workflow_id": recovery_payload.get(
                            "recovery_root_workflow_id"
                        ),
                        "failure_category": (
                            recovery_payload.get("failure_category")
                            or classify_failure(error_message).value
                        ),
                        "strategy": recovery_payload.get("strategy"),
                        "actual_cost": actual_cost,
                        "duration_ms": duration_ms,
                        "error_message": error_message,
                    },
                )
            )

        await session.commit()


@activity.defn
async def attempt_automatic_recovery(
    workflow_id: str,
    run_id: str,
    error_message: str,
) -> str:
    workflow_uuid = UUID(workflow_id)
    run_uuid = UUID(run_id)

    from titan.config import settings
    from titan.runtime.recovery import RecoveryPolicy
    from titan.runtime.recovery_service import start_recovery_workflow
    from titan.runtime.service import get_agent_runtime

    async with SessionFactory() as session:
        workflow = await session.scalar(
            select(WorkflowModel).where(WorkflowModel.id == workflow_uuid)
        )
        if workflow is None:
            return "ESCALATED:workflow_not_found"

        project = await session.scalar(
            select(ProjectModel).where(ProjectModel.id == workflow.project_id)
        )
        if project is None:
            return "ESCALATED:project_not_found"

        tasks = list(
            await session.scalars(
                select(TaskModel).where(
                    TaskModel.project_id == project.id,
                    TaskModel.workflow_id == workflow.id,
                )
            )
        )
        failed_tasks = [
            task
            for task in tasks
            if task.status in {"FAILED", "REPAIRING", "RETRYING", "BLOCKED"}
        ]
        if not failed_tasks:
            session.add(
                EventModel(
                    project_id=project.id,
                    type="RecoveryEscalated",
                    actor_type="SYSTEM",
                    aggregate_type="WORKFLOW",
                    aggregate_id=workflow.id,
                    payload={
                        "run_id": str(run_uuid),
                        "reason": "No failed or blocked tasks were found for recovery",
                        "error_message": error_message,
                    },
                )
            )
            await session.commit()
            return "ESCALATED:no_failed_tasks"

        prior_recovery_event = await session.scalar(
            select(EventModel)
            .where(
                EventModel.aggregate_type == "WORKFLOW",
                EventModel.aggregate_id == workflow.id,
                EventModel.type == "WorkflowRecoveryStarted",
            )
            .order_by(EventModel.occurred_at.desc())
            .limit(1)
        )
        current_attempt = int(
            (prior_recovery_event.payload or {}).get("recovery_attempt", 0)
        ) if prior_recovery_event is not None else 0

        failed_risks = tuple(task.risk_level for task in failed_tasks)
        approval_required = any(
            task.approval_requirement not in {"NONE", ""}
            for task in failed_tasks
        )
        policy = RecoveryPolicy(
            enabled=settings.recovery_auto_enabled,
            max_attempts=settings.recovery_max_attempts,
            min_autonomy_level=settings.recovery_min_autonomy_level,
            max_auto_risk_level=settings.recovery_max_auto_risk_level,
        )
        assessment = policy.assess(
            autonomy_level=project.autonomy_level,
            current_attempt=current_attempt,
            failed_risk_levels=failed_risks,
            approval_required=approval_required,
        )

        governance = GovernanceEngine()
        recovery_governance = governance.decide(
            (
                governance.check_recovery(assessment),
            )
        )
        await record_governance_decision(
            session,
            decision=recovery_governance,
            domain="RECOVERY",
            project_id=project.id,
            workflow_id=workflow.id,
            context={
                "recovery_attempt": assessment.next_attempt,
                "error_message": error_message,
                "failed_task_count": len(failed_tasks),
            },
        )

        if not recovery_governance.allowed:
            state = await session.scalar(
                select(ProjectStateModel).where(
                    ProjectStateModel.project_id == project.id
                )
            )
            if state is not None:
                state.status = "WAITING_HUMAN"
                state.phase = "RECOVERY_ESCALATED"
                state.version += 1

            session.add(
                EventModel(
                    project_id=project.id,
                    type="RecoveryEscalated",
                    actor_type="SYSTEM",
                    aggregate_type="WORKFLOW",
                    aggregate_id=workflow.id,
                    payload={
                        "run_id": str(run_uuid),
                        "reason": recovery_governance.reason,
                        "current_attempt": current_attempt,
                        "max_attempts": assessment.max_attempts,
                        "failed_task_ids": [str(task.id) for task in failed_tasks],
                        "failed_risk_levels": list(failed_risks),
                        "error_message": error_message,
                    },
                )
            )
            await session.commit()
            return f"ESCALATED:{assessment.reason}"

        recovery_category = classify_failure(error_message)
        history_events = list(
            await session.scalars(
                select(EventModel)
                .where(
                    EventModel.project_id == project.id,
                    EventModel.type.in_(
                        (
                            "RecoveryStarted",
                            "RecoveryResolved",
                            "RecoveryRepeatedFailure",
                            "RecoveryEscalated",
                            "RecoveryFailed",
                        )
                    ),
                )
                .order_by(EventModel.occurred_at.desc())
                .limit(50)
            )
        )
        observations = observations_from_events(history_events)
        strategy_selection = RecoveryStrategySelector().select(
            category=recovery_category,
            observations=observations,
        )

        session.add(
            EventModel(
                project_id=project.id,
                type="RecoveryStrategySelected",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={
                    "run_id": str(run_uuid),
                    "failure_category": recovery_category.value,
                    "strategy": strategy_selection.strategy.value,
                    "score": strategy_selection.score,
                    "reason": strategy_selection.reason,
                    "historical_observation_count": len(
                        [
                            observation
                            for observation in observations
                            if observation.category == recovery_category
                        ]
                    ),
                },
            )
        )
        await session.flush()

        runtime = get_agent_runtime()
        recovery_root = (
            str((prior_recovery_event.payload or {}).get("recovery_root_workflow_id"))
            if prior_recovery_event is not None
            and (prior_recovery_event.payload or {}).get("recovery_root_workflow_id")
            else workflow_id
        )

        try:
            result = await start_recovery_workflow(
                session,
                project=project,
                workflow=workflow,
                run_id=run_id,
                error_message=error_message,
                recovery_attempt=assessment.next_attempt,
                recovery_root_workflow_id=recovery_root,
                failure_category=recovery_category.value,
                strategy=strategy_selection.strategy,
                runtime=runtime,
            )
            await session.commit()
            return f"STARTED:{result.replacement_workflow_id}"
        except Exception as exc:
            await session.rollback()
            session.add(
                EventModel(
                    project_id=project.id,
                    type="RecoveryFailed",
                    actor_type="SYSTEM",
                    aggregate_type="WORKFLOW",
                    aggregate_id=workflow.id,
                    payload={
                        "recovery_attempt": assessment.next_attempt,
                        "failure_category": recovery_category.value,
                        "strategy": strategy_selection.strategy.value,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )
            )
            await session.commit()
            return f"FAILED:{type(exc).__name__}:{exc}"
