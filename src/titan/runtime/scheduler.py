from dataclasses import dataclass


RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


class TaskScheduleError(ValueError):
    """Base exception for invalid task scheduling input."""


class TaskScheduleCycleError(TaskScheduleError):
    """Raised when a dependency graph cannot be scheduled to completion."""


class TaskScheduleBudgetError(TaskScheduleError):
    """Raised when ready work cannot fit within the declared scheduling budget."""


class TaskScheduleProviderError(TaskScheduleError):
    """Raised when a task requires an unavailable model provider."""


@dataclass(frozen=True, slots=True)
class TaskSchedulingProfile:
    task_id: str
    risk_level: str = "R1"
    minimum_quality_tier: int = 1
    estimated_cost: float = 0.0
    priority: int = 0
    provider_available: bool = True


@dataclass(frozen=True, slots=True)
class TaskSchedule:
    waves: tuple[tuple[str, ...], ...]
    estimated_cost: float = 0.0

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task_id for wave in self.waves for task_id in wave)

    @property
    def max_parallelism(self) -> int:
        return max((len(wave) for wave in self.waves), default=0)


class DependencyAwareScheduler:
    """Build deterministic execution waves from dependencies and orchestration policy."""

    def build(
        self,
        task_ids: tuple[str, ...],
        dependencies: tuple[tuple[str, tuple[str, ...]], ...] = (),
        *,
        task_agents: tuple[tuple[str, str], ...] = (),
        agent_capacities: tuple[tuple[str, int], ...] = (),
        task_profiles: tuple[TaskSchedulingProfile, ...] = (),
        max_project_cost: float = 0.0,
    ) -> TaskSchedule:
        unique_task_ids = self._normalize_task_ids(task_ids)
        if max_project_cost < 0:
            raise TaskScheduleError("Project scheduling cost budget cannot be negative")

        dependency_map = self._normalize_dependencies(
            unique_task_ids,
            dependencies,
        )
        agent_map = self._normalize_task_map(
            unique_task_ids,
            task_agents,
            map_name="task agent map",
        )
        capacity_map = self._normalize_capacities(agent_capacities)
        profile_map = self._normalize_profiles(unique_task_ids, task_profiles)

        for task_id, profile in profile_map.items():
            if not profile.provider_available:
                raise TaskScheduleProviderError(
                    f"Task '{task_id}' cannot be scheduled because its required "
                    "model provider is unavailable"
                )

        critical_path = self._critical_path_lengths(unique_task_ids, dependency_map)
        position = {task_id: index for index, task_id in enumerate(unique_task_ids)}
        completed: set[str] = set()
        remaining = set(unique_task_ids)
        waves: list[tuple[str, ...]] = []
        estimated_cost = 0.0

        while remaining:
            ready = [
                task_id
                for task_id in unique_task_ids
                if task_id in remaining
                and dependency_map[task_id].issubset(completed)
            ]
            if not ready:
                unresolved = tuple(
                    task_id
                    for task_id in unique_task_ids
                    if task_id in remaining
                )
                raise TaskScheduleCycleError(
                    "Task dependency graph cannot make progress; "
                    f"unresolved tasks: {', '.join(unresolved)}"
                )

            ready.sort(
                key=lambda task_id: (
                    -critical_path[task_id],
                    -RISK_ORDER[profile_map[task_id].risk_level],
                    -profile_map[task_id].minimum_quality_tier,
                    -profile_map[task_id].priority,
                    profile_map[task_id].estimated_cost,
                    position[task_id],
                )
            )

            selected: list[str] = []
            agent_loads: dict[str, int] = {}
            budget_blocked = False

            for task_id in ready:
                profile = profile_map[task_id]
                agent = agent_map.get(task_id)
                capacity = capacity_map.get(agent) if agent is not None else None
                if capacity is not None and agent_loads.get(agent, 0) >= capacity:
                    continue

                if (
                    max_project_cost > 0
                    and estimated_cost + profile.estimated_cost > max_project_cost
                ):
                    budget_blocked = True
                    continue

                selected.append(task_id)
                estimated_cost += profile.estimated_cost
                if agent is not None and capacity is not None:
                    agent_loads[agent] = agent_loads.get(agent, 0) + 1

            if not selected:
                if budget_blocked and max_project_cost > 0:
                    raise TaskScheduleBudgetError(
                        "Ready tasks cannot fit within the declared project scheduling cost budget"
                    )
                raise TaskScheduleError(
                    "Ready tasks cannot be scheduled under the declared orchestration policy"
                )

            wave = tuple(selected)
            waves.append(wave)
            completed.update(wave)
            remaining.difference_update(wave)

        return TaskSchedule(
            waves=tuple(waves),
            estimated_cost=round(estimated_cost, 10),
        )

    @staticmethod
    def _normalize_task_ids(task_ids: tuple[str, ...]) -> tuple[str, ...]:
        normalized: list[str] = []
        seen: set[str] = set()
        for task_id in task_ids:
            if not task_id or not task_id.strip():
                raise TaskScheduleError("Task identifiers cannot be empty")
            cleaned = task_id.strip()
            if cleaned in seen:
                raise TaskScheduleError(
                    f"Duplicate task identifier '{cleaned}'"
                )
            seen.add(cleaned)
            normalized.append(cleaned)
        return tuple(normalized)

    @staticmethod
    def _normalize_dependencies(
        task_ids: tuple[str, ...],
        dependencies: tuple[tuple[str, tuple[str, ...]], ...],
    ) -> dict[str, set[str]]:
        task_set = set(task_ids)
        result = {task_id: set() for task_id in task_ids}
        for task_id, raw_dependencies in dependencies:
            if task_id not in task_set:
                raise TaskScheduleError(
                    f"Dependency map references unknown task '{task_id}'"
                )
            if task_id in raw_dependencies:
                raise TaskScheduleCycleError(
                    f"Task '{task_id}' cannot depend on itself"
                )

            normalized_dependencies = {
                dependency.strip()
                for dependency in raw_dependencies
                if dependency.strip()
            }
            unknown = normalized_dependencies.difference(task_set)
            if unknown:
                raise TaskScheduleError(
                    f"Task '{task_id}' depends on tasks outside the workflow: "
                    f"{', '.join(sorted(unknown))}"
                )
            result[task_id].update(normalized_dependencies)

        return result

    @staticmethod
    def _normalize_task_map(
        task_ids: tuple[str, ...],
        values: tuple[tuple[str, str], ...],
        *,
        map_name: str,
    ) -> dict[str, str]:
        task_set = set(task_ids)
        result: dict[str, str] = {}
        for task_id, agent_name in values:
            if task_id not in task_set:
                raise TaskScheduleError(
                    f"{map_name} references unknown task '{task_id}'"
                )
            if not agent_name or not agent_name.strip():
                raise TaskScheduleError(
                    f"{map_name} contains an empty agent name for task '{task_id}'"
                )
            cleaned = agent_name.strip()
            previous = result.get(task_id)
            if previous is not None and previous != cleaned:
                raise TaskScheduleError(
                    f"{map_name} assigns multiple agents to task '{task_id}'"
                )
            result[task_id] = cleaned
        return result

    @staticmethod
    def _normalize_capacities(
        values: tuple[tuple[str, int], ...],
    ) -> dict[str, int]:
        result: dict[str, int] = {}
        for agent_name, capacity in values:
            if not agent_name or not agent_name.strip():
                raise TaskScheduleError("Agent capacity entries require a name")
            if capacity < 1:
                raise TaskScheduleError(
                    f"Agent '{agent_name}' must have a concurrency capacity of at least 1"
                )
            cleaned = agent_name.strip()
            previous = result.get(cleaned)
            if previous is not None and previous != capacity:
                raise TaskScheduleError(
                    f"Agent '{cleaned}' has conflicting concurrency capacities"
                )
            result[cleaned] = capacity
        return result

    @staticmethod
    def _normalize_profiles(
        task_ids: tuple[str, ...],
        values: tuple[TaskSchedulingProfile, ...],
    ) -> dict[str, TaskSchedulingProfile]:
        task_set = set(task_ids)
        result = {
            task_id: TaskSchedulingProfile(task_id=task_id)
            for task_id in task_ids
        }
        for profile in values:
            if profile.task_id not in task_set:
                raise TaskScheduleError(
                    f"Task scheduling profile references unknown task '{profile.task_id}'"
                )
            if profile.risk_level not in RISK_ORDER:
                raise TaskScheduleError(
                    f"Task '{profile.task_id}' has unsupported risk level "
                    f"'{profile.risk_level}'"
                )
            if profile.minimum_quality_tier < 0:
                raise TaskScheduleError(
                    f"Task '{profile.task_id}' has an invalid quality tier"
                )
            if profile.estimated_cost < 0:
                raise TaskScheduleError(
                    f"Task '{profile.task_id}' has a negative estimated cost"
                )
            if profile.task_id in values_by_task_id(result):
                previous = result[profile.task_id]
                if previous != TaskSchedulingProfile(task_id=profile.task_id) and previous != profile:
                    raise TaskScheduleError(
                        f"Task '{profile.task_id}' has multiple scheduling profiles"
                    )
            result[profile.task_id] = profile
        return result

    @staticmethod
    def _critical_path_lengths(
        task_ids: tuple[str, ...],
        dependency_map: dict[str, set[str]],
    ) -> dict[str, int]:
        dependents: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
        for task_id, dependencies in dependency_map.items():
            for dependency in dependencies:
                dependents[dependency].append(task_id)

        memo: dict[str, int] = {}
        visiting: set[str] = set()

        def depth(task_id: str) -> int:
            if task_id in memo:
                return memo[task_id]
            if task_id in visiting:
                raise TaskScheduleCycleError(
                    f"Task dependency graph contains a cycle involving '{task_id}'"
                )

            visiting.add(task_id)
            children = dependents[task_id]
            memo[task_id] = (
                0
                if not children
                else 1 + max(depth(child) for child in children)
            )
            visiting.remove(task_id)
            return memo[task_id]

        for task_id in task_ids:
            depth(task_id)

        return memo


def values_by_task_id(
    profiles: dict[str, TaskSchedulingProfile],
) -> set[str]:
    return set(profiles)
