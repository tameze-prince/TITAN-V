from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.config import settings
from titan.persistence.models import (
    AgentModel,
    EventModel,
    ProjectModel,
    TaskModel,
    WorkflowModel,
    task_dependencies,
)
from titan.runtime.governance import task_requires_human_approval
from titan.runtime.model_router import BudgetExceeded, ModelBudget, ModelSelectionRequest
from titan.runtime.scheduler import DependencyAwareScheduler, TaskSchedulingProfile
from titan.runtime.service import AgentRuntime
from titan.workflows.contracts import WorkflowInput, WorkflowTaskProfile


async def build_workflow_input(
    session: AsyncSession,
    *,
    project: ProjectModel,
    workflow: WorkflowModel,
    tasks: list[TaskModel],
    runtime: AgentRuntime,
    precompleted_task_ids: tuple[str, ...] = (),
    recovery_attempt: int = 0,
    recovery_root_workflow_id: str | None = None,
) -> WorkflowInput:
    requested_ids = tuple(str(task.id) for task in tasks)
    requested_id_set = set(requested_ids)
    tasks_by_id = {str(task.id): task for task in tasks}

    dependency_rows = list(
        await session.execute(
            select(
                task_dependencies.c.task_id,
                task_dependencies.c.depends_on_task_id,
            ).where(
                task_dependencies.c.task_id.in_([task.id for task in tasks])
            )
        )
    )
    dependency_map: dict[str, list[str]] = {task_id: [] for task_id in requested_ids}
    for task_id, dependency_id in dependency_rows:
        dependency_str = str(dependency_id)
        if dependency_str not in requested_id_set:
            raise ValueError(
                f"Task {task_id} has a dependency outside the workflow task set"
            )
        dependency_map[str(task_id)].append(dependency_str)

    history_rows = list(
        await session.scalars(
            select(EventModel)
            .where(
                EventModel.project_id == project.id,
                EventModel.type == "ModelUsageRecorded",
                EventModel.aggregate_type == "TASK",
                EventModel.aggregate_id.in_([task.id for task in tasks]),
            )
            .order_by(EventModel.occurred_at.desc())
        )
    )
    usage_history: dict[tuple[UUID, str], list[tuple[float | None, int | None]]] = {}
    for event in history_rows:
        payload = event.payload or {}
        model = str(payload.get("model") or "")
        if not model:
            continue
        usage = payload.get("usage") or {}
        cost = usage.get("estimated_cost")
        duration = payload.get("duration_ms")
        if duration is None:
            duration = usage.get("elapsed_ms")
        try:
            parsed_cost = float(cost) if cost is not None else None
        except (TypeError, ValueError):
            parsed_cost = None
        try:
            parsed_duration = int(duration) if duration is not None else None
        except (TypeError, ValueError):
            parsed_duration = None
        usage_history.setdefault((event.aggregate_id, model), []).append(
            (parsed_cost, parsed_duration)
        )

    owner_agent_ids = {task.owner_agent_id for task in tasks if task.owner_agent_id is not None}
    agent_rows = (
        list(
            await session.scalars(
                select(AgentModel).where(AgentModel.id.in_(owner_agent_ids))
            )
        )
        if owner_agent_ids
        else []
    )
    agents_by_id = {agent.id: agent for agent in agent_rows}

    task_agents: list[tuple[str, str]] = []
    used_agents: dict[str, int] = {}
    task_profiles: list[WorkflowTaskProfile] = []

    for task in tasks:
        if task.owner_agent_id is None:
            contract = runtime.contracts.resolve("general-executor")
            agent_name = contract.name
            metadata = {
                "max_concurrency": contract.max_concurrency,
                "minimum_quality_tier": contract.minimum_quality_tier,
                "scheduling_priority": contract.scheduling_priority,
                "model": contract.model,
            }
        else:
            agent = agents_by_id.get(task.owner_agent_id)
            if agent is None:
                raise ValueError(f"Assigned agent for task {task.id} is not available")
            agent_name = agent.name
            metadata = agent.metadata_json or {}

        task_id = str(task.id)
        task_agents.append((task_id, agent_name))

        try:
            capacity = max(1, int(metadata.get("max_concurrency", 1)))
        except (TypeError, ValueError):
            capacity = 1
        used_agents[agent_name] = capacity

        try:
            minimum_quality_tier = max(0, int(metadata.get("minimum_quality_tier", 1)))
        except (TypeError, ValueError):
            minimum_quality_tier = 1

        try:
            priority = int(metadata.get("scheduling_priority", 0))
        except (TypeError, ValueError):
            priority = 0

        preferred_model = str(metadata.get("model") or "local")
        provider_available = True
        estimated_cost = 0.0
        expected_duration_ms = 0

        try:
            selection = runtime.model_router.select(
                ModelSelectionRequest(
                    preferred_model=preferred_model,
                    minimum_quality_tier=minimum_quality_tier,
                    budget=ModelBudget(
                        max_input_tokens=settings.model_max_input_tokens,
                        max_output_tokens=settings.model_max_output_tokens,
                        max_cost=0.0,
                    ),
                )
            )
            fallback_cost = runtime.model_router.estimate_cost(
                selection.route,
                {
                    "input_tokens": settings.model_max_input_tokens,
                    "output_tokens": settings.model_max_output_tokens,
                },
            )
            history = usage_history.get((task.id, selection.route.model), ())[:5]
            observed_costs = [value for value, _ in history if value is not None]
            observed_durations = [value for _, value in history if value is not None]
            estimated_cost = (
                sum(observed_costs) / len(observed_costs)
                if observed_costs
                else fallback_cost
            )
            expected_duration_ms = (
                round(sum(observed_durations) / len(observed_durations))
                if observed_durations
                else 0
            )
        except (BudgetExceeded, KeyError, LookupError, ValueError):
            provider_available = False

        task_profiles.append(
            WorkflowTaskProfile(
                task_id=task_id,
                risk_level=task.risk_level,
                minimum_quality_tier=minimum_quality_tier,
                estimated_cost=estimated_cost,
                expected_duration_ms=expected_duration_ms,
                priority=priority,
                provider_available=provider_available,
            )
        )

    request = WorkflowInput(
        workflow_id=str(workflow.id),
        project_id=str(project.id),
        task_ids=requested_ids,
        dependencies=tuple(
            (task_id, tuple(sorted(dependency_map[task_id])))
            for task_id in requested_ids
        ),
        task_agents=tuple(task_agents),
        agent_capacities=tuple(sorted(used_agents.items())),
        task_profiles=tuple(task_profiles),
        max_project_cost=settings.orchestration_max_cost,
        precompleted_task_ids=tuple(precompleted_task_ids),
        approval_task_ids=tuple(
            task_id
            for task_id in requested_ids
            if task_requires_human_approval(
                risk_level=tasks_by_id[task_id].risk_level,
                approval_requirement=tasks_by_id[task_id].approval_requirement,
                approval_quorum=tasks_by_id[task_id].approval_quorum,
            )
        ),
        approval_quorums=tuple(
            (
                task_id,
                max(1, tasks_by_id[task_id].approval_quorum),
            )
            for task_id in requested_ids
            if task_requires_human_approval(
                risk_level=tasks_by_id[task_id].risk_level,
                approval_requirement=tasks_by_id[task_id].approval_requirement,
            )
        ),
        approval_timeout_seconds=max(1, settings.human_approval_timeout_seconds),
        recovery_attempt=recovery_attempt,
        recovery_root_workflow_id=recovery_root_workflow_id,
    )

    schedule = DependencyAwareScheduler().build(
        requested_ids,
        tuple(
            (task_id, tuple(sorted(dependency_map[task_id])))
            for task_id in requested_ids
        ),
        task_agents=tuple(task_agents),
        agent_capacities=tuple(sorted(used_agents.items())),
        task_profiles=tuple(
            TaskSchedulingProfile(
                task_id=profile.task_id,
                risk_level=profile.risk_level,
                minimum_quality_tier=profile.minimum_quality_tier,
                estimated_cost=profile.estimated_cost,
                expected_duration_ms=profile.expected_duration_ms,
                priority=profile.priority,
                provider_available=profile.provider_available,
            )
            for profile in task_profiles
        ),
        max_project_cost=settings.orchestration_max_cost,
        precompleted_task_ids=tuple(precompleted_task_ids),
    )

    await session.flush()
    return request
