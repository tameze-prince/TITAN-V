from dataclasses import dataclass


class TaskScheduleError(ValueError):
    """Base exception for invalid task scheduling input."""


class TaskScheduleCycleError(TaskScheduleError):
    """Raised when a dependency graph cannot be scheduled to completion."""


@dataclass(frozen=True, slots=True)
class TaskSchedule:
    waves: tuple[tuple[str, ...], ...]

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task_id for wave in self.waves for task_id in wave)

    @property
    def max_parallelism(self) -> int:
        return max((len(wave) for wave in self.waves), default=0)


class DependencyAwareScheduler:
    """Build deterministic parallel execution waves from a task dependency DAG."""

    def build(
        self,
        task_ids: tuple[str, ...],
        dependencies: tuple[tuple[str, tuple[str, ...]], ...] = (),
    ) -> TaskSchedule:
        unique_task_ids = self._normalize_task_ids(task_ids)
        task_set = set(unique_task_ids)
        dependency_map = self._normalize_dependencies(
            unique_task_ids,
            dependencies,
        )

        completed: set[str] = set()
        remaining = set(unique_task_ids)
        waves: list[tuple[str, ...]] = []

        while remaining:
            ready = tuple(
                task_id
                for task_id in unique_task_ids
                if task_id in remaining
                and dependency_map[task_id].issubset(completed)
            )
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

            waves.append(ready)
            completed.update(ready)
            remaining.difference_update(ready)

        return TaskSchedule(waves=tuple(waves))

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
