from collections.abc import Sequence
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import (
    AgentModel,
    EventModel,
    IntentRecordModel,
    ProjectModel,
    ProjectStateModel,
    TaskGraphModel,
    TaskModel,
    task_dependencies,
)
from titan.runtime.contracts import AgentContract
from titan.runtime.intent import IntentRepresentation
from titan.runtime.memory import MemoryStore
from titan.runtime.planner import TaskGraphPlan, topological_order


async def persist_task_graph(
    session: AsyncSession,
    *,
    project: ProjectModel,
    intent_record: IntentRecordModel,
    intent: IntentRepresentation,
    plan: TaskGraphPlan,
    contracts: Sequence[AgentContract],
) -> tuple[TaskGraphModel, tuple[TaskModel, ...]]:
    if project.id != intent_record.project_id:
        raise ValueError("Intent record does not belong to project")
    if intent_record.project_id != project.id:
        raise ValueError("Intent record project mismatch")

    await _upsert_agent_models(session, contracts)

    graph = TaskGraphModel(
        project_id=project.id,
        intent_record_id=intent_record.id,
        name=plan.name,
        version=plan.version,
        status="READY",
        objective=plan.objective,
        plan_json=plan.model_dump(mode="json"),
    )
    session.add(graph)
    await session.flush()

    await session.execute(
        TaskGraphModel.__table__.update()
        .where(
            TaskGraphModel.project_id == project.id,
            TaskGraphModel.id != graph.id,
            TaskGraphModel.status == "READY",
        )
        .values(status="SUPERSEDED")
    )

    agent_rows = {
        row.name: row
        for row in (
            await session.scalars(
                select(AgentModel).where(
                    AgentModel.name.in_(
                        {node.agent_name for node in plan.nodes}
                    )
                )
            )
        )
    }

    tasks_by_key: dict[str, TaskModel] = {}
    ordered_nodes = topological_order(plan.nodes)
    for node in ordered_nodes:
        agent = agent_rows.get(node.agent_name)
        if agent is None:
            raise ValueError(f"Assigned agent '{node.agent_name}' is not persisted")

        task = TaskModel(
            project_id=project.id,
            task_graph_id=graph.id,
            task_key=node.key,
            position=node.position,
            owner_agent_id=agent.id,
            title=node.title,
            objective=node.objective,
            status="PENDING",
            risk_level=node.risk_level,
            approval_requirement=node.approval_requirement,
            approval_quorum=node.approval_quorum,
            required_capabilities=list(node.required_capabilities),
        )
        session.add(task)
        tasks_by_key[node.key] = task

    await session.flush()

    dependency_rows = []
    for node in plan.nodes:
        for dependency_key in node.dependencies:
            dependency_rows.append(
                {
                    "task_id": tasks_by_key[node.key].id,
                    "depends_on_task_id": tasks_by_key[dependency_key].id,
                }
            )

    if dependency_rows:
        await session.execute(task_dependencies.insert(), dependency_rows)

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
        "intent_record_id": str(intent_record.id),
        "task_graph_id": str(graph.id),
        "task_graph_version": plan.version,
        "objective": intent.desired_outcome or intent.problem,
        "unknowns": list(intent.unknowns),
        "constraints": list(intent.constraints),
        "risks": list(intent.risks),
        "task_count": len(ordered_nodes),
        "assigned_agents": sorted(
            {node.agent_name for node in ordered_nodes}
        ),
    }

    project.current_phase = "EXECUTION_READY"

    memory = MemoryStore()
    await memory.remember(
        session,
        project_id=project.id,
        task_id=None,
        kind="TASK_GRAPH",
        content=(
            f"Task graph v{plan.version} created with {len(plan.nodes)} tasks. "
            f"Objective: {plan.objective}"
        ),
        importance=95,
        source_type="TASK_PLANNER",
        source_id=graph.id,
        metadata={
            "intent_record_id": str(intent_record.id),
            "task_graph_version": plan.version,
            "task_count": len(plan.nodes),
            "assigned_agents": sorted(
                {node.agent_name for node in plan.nodes}
            ),
        },
    )

    session.add(
        EventModel(
            project_id=project.id,
            type="TaskGraphPlanned",
            actor_type="SYSTEM",
            aggregate_type="TASK_GRAPH",
            aggregate_id=graph.id,
            payload={
                "intent_record_id": str(intent_record.id),
                "version": plan.version,
                "task_count": len(plan.nodes),
                "task_ids": [
                    str(tasks_by_key[node.key].id)
                    for node in ordered_nodes
                ],
                "assigned_agents": sorted(
                    {node.agent_name for node in plan.nodes}
                ),
                "unknowns": list(plan.unknowns),
                "risks": list(plan.risks),
            },
        )
    )
    return graph, tuple(tasks_by_key[node.key] for node in ordered_nodes)


async def _upsert_agent_models(
    session: AsyncSession,
    contracts: Sequence[AgentContract],
) -> None:
    if not contracts:
        return

    values = [
        {
            "name": contract.name,
            "role": contract.role,
            "version": contract.version,
            "status": "ACTIVE",
            "metadata_json": {
                "capabilities": list(contract.capabilities),
                "allowed_tools": list(contract.allowed_tools),
                "risk_ceiling": contract.risk_ceiling,
                "model": contract.model,
                "minimum_quality_tier": contract.minimum_quality_tier,
                "max_concurrency": contract.max_concurrency,
                "scheduling_priority": contract.scheduling_priority,
            },
        }
        for contract in contracts
    ]

    statement = pg_insert(AgentModel).values(values)
    statement = statement.on_conflict_do_update(
        index_elements=[AgentModel.name],
        set_={
            "role": statement.excluded.role,
            "version": statement.excluded.version,
            "status": statement.excluded.status,
            "metadata_json": statement.excluded.metadata_json,
        },
    )
    await session.execute(statement)
