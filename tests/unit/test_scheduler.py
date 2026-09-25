import pytest

from titan.runtime.scheduler import (
    DependencyAwareScheduler,
    TaskScheduleCycleError,
    TaskScheduleError,
)


def test_scheduler_groups_independent_tasks_into_parallel_waves() -> None:
    scheduler = DependencyAwareScheduler()

    schedule = scheduler.build(
        ("a", "b", "c", "d", "e"),
        (
            ("c", ("a",)),
            ("d", ("b",)),
        ),
    )

    assert schedule.waves == (
        ("a", "b"),
        ("c", "d"),
    )
    assert schedule.max_parallelism == 2


def test_scheduler_is_deterministic_for_dependency_order() -> None:
    scheduler = DependencyAwareScheduler()

    schedule = scheduler.build(
        ("z", "a", "m"),
        (
            ("m", ("z",)),
        ),
    )

    assert schedule.waves == (
        ("z", "a"),
        ("m",),
    )


def test_scheduler_respects_agent_concurrency_capacity() -> None:
    scheduler = DependencyAwareScheduler()

    schedule = scheduler.build(
        ("a", "b", "c"),
        task_agents=(
            ("a", "general-executor"),
            ("b", "general-executor"),
            ("c", "engineering-executor"),
        ),
        agent_capacities=(
            ("general-executor", 1),
            ("engineering-executor", 1),
        ),
    )

    assert schedule.waves == (
        ("a", "c"),
        ("b",),
    )


def test_scheduler_prioritizes_the_critical_path_when_capacity_is_limited() -> None:
    scheduler = DependencyAwareScheduler()

    schedule = scheduler.build(
        ("a", "b", "c", "d"),
        (
            ("c", ("a",)),
            ("d", ("c",)),
        ),
        task_agents=(
            ("a", "general-executor"),
            ("b", "general-executor"),
            ("c", "general-executor"),
            ("d", "general-executor"),
        ),
        agent_capacities=(("general-executor", 1),),
    )

    assert schedule.waves == (
        ("a",),
        ("c",),
        ("d",),
        ("e",),
        ("b",),
    )


def test_scheduler_rejects_invalid_capacity() -> None:
    scheduler = DependencyAwareScheduler()

    with pytest.raises(TaskScheduleError, match="at least 1"):
        scheduler.build(
            ("a",),
            task_agents=(("a", "general-executor"),),
            agent_capacities=(("general-executor", 0),),
        )


def test_scheduler_rejects_dependencies_outside_workflow() -> None:
    scheduler = DependencyAwareScheduler()

    with pytest.raises(TaskScheduleError, match="outside the workflow"):
        scheduler.build(
            ("a",),
            (("a", ("external",)),),
        )


def test_scheduler_rejects_cycles() -> None:
    scheduler = DependencyAwareScheduler()

    with pytest.raises(TaskScheduleCycleError):
        scheduler.build(
            ("a", "b"),
            (
                ("a", ("b",)),
                ("b", ("a",)),
            ),
        )


def test_scheduler_rejects_duplicate_tasks() -> None:
    scheduler = DependencyAwareScheduler()

    with pytest.raises(TaskScheduleError, match="Duplicate"):
        scheduler.build(("a", "a"))
