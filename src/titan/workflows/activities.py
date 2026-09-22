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
from titan.runtime.memory import MemoryStore
from titan.runtime.repair import AgentEvaluationFailure
from titan.runtime.service import get_agent_runtime


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

        state = await session.scalar(
            select(ProjectStateModel).where(
                ProjectStateModel.project_id == workflow.project_id
            )
        )
        if state is not None:
            state.status = "COMPLETED"
            state.phase = "COMPLETED"
            state.version += 1

        if workflow.task_graph_id is not None:
            task_graph = await session.scalar(
                select(TaskGraphModel).where(
                    TaskGraphModel.id == workflow.task_graph_id
                )
            )
            if task_graph is not None:
                task_graph.status = "COMPLETED"

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

        state = await session.scalar(
            select(ProjectStateModel).where(
                ProjectStateModel.project_id == workflow.project_id
            )
        )
        if state is not None:
            state.status = "FAILED"
            state.phase = "EXECUTION_FAILED"
            state.version += 1

        if workflow.task_graph_id is not None:
            task_graph = await session.scalar(
                select(TaskGraphModel).where(
                    TaskGraphModel.id == workflow.task_graph_id
                )
            )
            if task_graph is not None:
                task_graph.status = "FAILED"

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
        await session.commit()
