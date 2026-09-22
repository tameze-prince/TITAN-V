from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from temporalio import activity

from titan.persistence.database import SessionFactory
from titan.persistence.models import ArtifactModel, EventModel, RunModel, TaskModel, WorkflowModel
from titan.runtime.contracts import AgentTaskContext
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
        task = await session.scalar(select(TaskModel).where(TaskModel.id == task_uuid))
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        if task.workflow_id != workflow_uuid:
            raise ValueError(f"Task {task_id} does not belong to workflow {workflow_id}")

        if task.status == "COMPLETED":
            return True

        task.status = "RUNNING"
        session.add(
            EventModel(
                project_id=task.project_id,
                type="TaskStarted",
                actor_type="SYSTEM",
                aggregate_type="TASK",
                aggregate_id=task.id,
                payload={"run_id": run_id, "execution_mode": "agent-runtime"},
            )
        )
        await session.flush()

        runtime = get_agent_runtime()
        context = AgentTaskContext(
            task_id=task_id,
            run_id=run_id,
            project_id=str(task.project_id),
            title=task.title,
            objective=task.objective,
            risk_level=task.risk_level,
        )

        try:
            execution = await runtime.execute(context)

            artifact = ArtifactModel(
                project_id=task.project_id,
                type="AGENT_RESULT",
                title=f"{task.title} — agent result",
                status="FINAL",
                media_type="application/json",
                content_ref=execution.model_dump_json(),
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
                    type="ArtifactCreated",
                    actor_type="SYSTEM",
                    aggregate_type="ARTIFACT",
                    aggregate_id=artifact.id,
                    payload={
                        "task_id": task_id,
                        "artifact_type": artifact.type,
                        "checksum_pending": True,
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
        except Exception as exc:
            task.status = "FAILED"
            session.add(
                EventModel(
                    project_id=task.project_id,
                    type="TaskFailed",
                    actor_type="SYSTEM",
                    aggregate_type="TASK",
                    aggregate_id=task.id,
                    payload={
                        "run_id": run_id,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
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
