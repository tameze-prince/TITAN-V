from copy import deepcopy
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from titan.persistence.models import (
    AgentModel,
    EventModel,
    ProjectModel,
    ProjectStateModel,
    TaskGraphModel,
    TaskModel,
    WorkflowModel,
    task_dependencies,
)
from titan.runtime.capabilities import CapabilityRegistry
from titan.runtime.contracts import AgentContract
from titan.runtime.memory import MemoryStore
from titan.runtime.replanner import AdaptiveReplanner, ReplanDecision


async def replan_failed_workflow(
    session: AsyncSession,
    *,
    project: ProjectModel,
    workflow: WorkflowModel,
    capability_registry: CapabilityRegistry,
    contracts: Sequence[AgentContract],
    allow_reassignment: bool = True,
    recovery_strategy: str = "REPLAN_REASSIGN",
) -> tuple[TaskGraphModel, tuple[TaskModel, ...], ReplanDecision]:
    if workflow.project_id != project.id:
        raise ValueError("Workflow does not belong to project")
    if workflow.task_graph_id is None:
        raise ValueError("Workflow is not linked to a task graph")
    if workflow.status != "FAILED":
        raise ValueError(
            f"Only failed workflows can be replanned; current status is {workflow.status}"
        )

    graph = await session.scalar(
        select(TaskGraphModel).where(TaskGraphModel.id == workflow.task_graph_id)
    )
    if graph is None:
        raise ValueError("Workflow task graph not found")

    old_tasks = list(
        await session.scalars(
            select(TaskModel)
            .options(selectinload(TaskModel.owner_agent))
            .where(
                TaskModel.project_id == project.id,
                TaskModel.task_graph_id == graph.id,
            )
            .order_by(TaskModel.position.asc())
        )
    )
    if not old_tasks:
        raise ValueError("Task graph contains no tasks")

    old_task_ids = {task.id: task for task in old_tasks}
    dependency_rows = list(
        await session.execute(
            select(
                task_dependencies.c.task_id,
                task_dependencies.c.depends_on_task_id,
            ).where(
                task_dependencies.c.task_id.in_(old_task_ids)
            )
        )
    )
    dependencies_by_task: dict[str, list[str]] = {
        str(task.id): []
        for task in old_tasks
    }
    for task_id, dependency_id in dependency_rows:
        dependencies_by_task[str(task_id)].append(str(dependency_id))

    failed_tasks = tuple(
        str(task.id)
        for task in old_tasks
        if task.status in {"FAILED", "REPAIRING", "RETRYING", "BLOCKED"}
    )
    if not failed_tasks:
        raise ValueError(
            "The failed workflow has no failed or blocked task suitable for adaptive replanning"
        )

    task_metadata = tuple(
        (
            str(task.id),
            tuple(task.required_capabilities),
            task.risk_level,
            task.owner_agent.name if task.owner_agent is not None else None,
        )
        for task in old_tasks
    )
    replanner = AdaptiveReplanner(capability_registry, tuple(contracts))
    decision = replanner.analyze(
        task_ids=tuple(str(task.id) for task in old_tasks),
        dependencies=tuple(
            (task_id, tuple(dependencies))
            for task_id, dependencies in dependencies_by_task.items()
        ),
        failed_task_ids=failed_tasks,
        task_metadata=task_metadata,
        allow_reassignment=allow_reassignment,
    )

    version = await session.scalar(
        select(func.max(TaskGraphModel.version)).where(
            TaskGraphModel.project_id == project.id
        )
    )
    next_version = int(version or graph.version) + 1

    reassignment_map = {
        item.task_id: item.new_agent
        for item in decision.reassignments
    }
    agent_names = {
        task.owner_agent.name
        for task in old_tasks
        if task.owner_agent is not None
    }
    agent_names.update(reassignment_map.values())
    agent_rows = {
        row.name: row
        for row in (
            await session.scalars(
                select(AgentModel).where(AgentModel.name.in_(agent_names))
            )
        )
    }

    plan_json = deepcopy(graph.plan_json or {})
    plan_json["version"] = next_version
    plan_json["name"] = f"Adaptive replan of {graph.name}"
    plan_json["replan"] = {
        "strategy": recovery_strategy,
        "source_graph_id": str(graph.id),
        "source_graph_version": graph.version,
        "failed_task_ids": list(decision.failed_task_ids),
        "impacted_task_ids": list(decision.impacted_task_ids),
        "reassignments": [
            {
                "task_id": item.task_id,
                "previous_agent": item.previous_agent,
                "new_agent": item.new_agent,
                "reason": item.reason,
            }
            for item in decision.reassignments
        ],
        "rationale": decision.rationale,
    }

    for node in plan_json.get("nodes", []):
        task_key = node.get("key")
        old_task = next(
            (task for task in old_tasks if task.task_key == task_key),
            None,
        )
        if old_task is None:
            continue
        replacement = reassignment_map.get(str(old_task.id))
        if replacement:
            node["agent_name"] = replacement

    new_graph = TaskGraphModel(
        project_id=project.id,
        intent_record_id=graph.intent_record_id,
        name=plan_json.get("name", f"Adaptive replan of {graph.name}"),
        version=next_version,
        status="READY",
        objective=graph.objective,
        plan_json=plan_json,
    )
    session.add(new_graph)
    await session.flush()

    await session.execute(
        TaskGraphModel.__table__.update()
        .where(
            TaskGraphModel.project_id == project.id,
            TaskGraphModel.id != new_graph.id,
            TaskGraphModel.status == "READY",
        )
        .values(status="SUPERSEDED")
    )

    new_tasks_by_old_id: dict[str, TaskModel] = {}
    impacted_set = set(decision.impacted_task_ids)

    for old_task in old_tasks:
        old_id = str(old_task.id)
        replacement_name = reassignment_map.get(old_id)
        owner_agent = (
            agent_rows.get(replacement_name)
            if replacement_name is not None
            else old_task.owner_agent
        )
        if replacement_name is not None and owner_agent is None:
            raise ValueError(
                f"Reassigned agent '{replacement_name}' is not persisted"
            )

        status = (
            "PENDING"
            if old_id in impacted_set
            else ("COMPLETED" if old_task.status == "COMPLETED" else "PENDING")
        )
        new_task = TaskModel(
            project_id=project.id,
            task_graph_id=new_graph.id,
            task_key=old_task.task_key,
            position=old_task.position,
            owner_agent_id=owner_agent.id if owner_agent is not None else None,
            title=old_task.title,
            objective=old_task.objective,
            status=status,
            risk_level=old_task.risk_level,
            approval_requirement=old_task.approval_requirement,
            required_capabilities=list(old_task.required_capabilities),
        )
        session.add(new_task)
        new_tasks_by_old_id[old_id] = new_task

    await session.flush()

    dependency_values = []
    for old_task_id, dependency_ids in dependencies_by_task.items():
        for dependency_id in dependency_ids:
            dependency_values.append(
                {
                    "task_id": new_tasks_by_old_id[old_task_id].id,
                    "depends_on_task_id": new_tasks_by_old_id[dependency_id].id,
                }
            )
    if dependency_values:
        await session.execute(task_dependencies.insert(), dependency_values)

    state = await session.scalar(
        select(ProjectStateModel).where(ProjectStateModel.project_id == project.id)
    )
    if state is None:
        state = ProjectStateModel(
            project_id=project.id,
            status="READY",
            phase="EXECUTION_READY",
            version=1,
        )
        session.add(state)
    else:
        state.version += 1

    state.status = "READY"
    state.phase = "EXECUTION_READY"
    state.state_json = {
        **state.state_json,
        "task_graph_id": str(new_graph.id),
        "task_graph_version": next_version,
        "replanned_from_graph_id": str(graph.id),
        "failed_task_ids": list(decision.failed_task_ids),
        "impacted_task_ids": list(decision.impacted_task_ids),
        "reassignments": [
            {
                "task_id": item.task_id,
                "previous_agent": item.previous_agent,
                "new_agent": item.new_agent,
            }
            for item in decision.reassignments
        ],
    }
    project.current_phase = "EXECUTION_READY"

    await MemoryStore().remember(
        session,
        project_id=project.id,
        task_id=None,
        kind="TASK_GRAPH_REPLAN",
        content=(
            f"Adaptive replan v{next_version} created from graph v{graph.version}. "
            f"Failed tasks: {', '.join(decision.failed_task_ids)}"
        ),
        importance=98,
        source_type="ADAPTIVE_REPLANNER",
        source_id=new_graph.id,
        metadata={
            "source_graph_id": str(graph.id),
            "failed_task_ids": list(decision.failed_task_ids),
            "impacted_task_ids": list(decision.impacted_task_ids),
            "reassignments": [
                {
                    "task_id": item.task_id,
                    "previous_agent": item.previous_agent,
                    "new_agent": item.new_agent,
                }
                for item in decision.reassignments
            ],
            "strategy": recovery_strategy,
        },
    )

    session.add(
        EventModel(
            project_id=project.id,
            type="TaskGraphReplanned",
            actor_type="SYSTEM",
            aggregate_type="TASK_GRAPH",
            aggregate_id=new_graph.id,
            payload={
                "source_graph_id": str(graph.id),
                "source_graph_version": graph.version,
                "new_version": next_version,
                "failed_task_ids": list(decision.failed_task_ids),
                "impacted_task_ids": list(decision.impacted_task_ids),
                "reassignments": [
                    {
                        "task_id": item.task_id,
                        "previous_agent": item.previous_agent,
                        "new_agent": item.new_agent,
                    }
                    for item in decision.reassignments
                ],
                "rationale": decision.rationale,
                "strategy": recovery_strategy,
            },
        )
    )

    await session.commit()
    return new_graph, tuple(
        new_tasks_by_old_id[str(task.id)]
        for task in old_tasks
    ), decision
