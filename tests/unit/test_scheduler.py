import pytest

from titan.runtime.scheduler import (
    DependencyAwareScheduler,
    TaskScheduleBudgetError,
    TaskScheduleCycleError,
    TaskScheduleError,
    TaskScheduleProviderError,
    TaskSchedulingProfile,
)


def test_scheduler_groups_independent_tasks_into_parallel_waves() -> None:
    scheduler = DependencyAwareScheduler()

    schedule = scheduler.build(
        ("a", "b", "c", "d"),
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
        ("a", "b", "c", "d", "e"),
        (
            ("c", ("a",)),
            ("d", ("c",)),
            ("e", ("d",)),
        ),
        task_agents=(
            ("a", "general-executor"),
            ("b", "general-executor"),
            ("c", "general-executor"),
            ("d", "general-executor"),
            ("e", "general-executor"),
        ),
        agent_capacities=(("general-executor", 1),),
    )

    assert schedule.waves == (
        ("a",),
        ("c",),
        ("d",),
        ("b",),
        ("e",),
    )


def test_scheduler_orders_ready_tasks_by_risk_quality_and_priority() -> None:
    scheduler = DependencyAwareScheduler()

    schedule = scheduler.build(
        ("low", "high"),
        task_agents=(
            ("low", "general-executor"),
            ("high", "general-executor"),
        ),
        agent_capacities=(("general-executor", 1),),
        task_profiles=(
            TaskSchedulingProfile(
                task_id="low",
                risk_level="R1",
                minimum_quality_tier=1,
                priority=0,
                estimated_cost=1.0,
                expected_duration_ms=100,
            ),
            TaskSchedulingProfile(
                task_id="high",
                risk_level="R4",
                minimum_quality_tier=3,
                priority=10,
                estimated_cost=5.0,
                expected_duration_ms=500,
            ),
        ),
    )

    assert schedule.waves == (("high",), ("low",))
    assert schedule.estimated_cost == 6.0
    assert schedule.estimated_makespan_ms == 600


def test_scheduler_enforces_project_cost_budget() -> None:
    scheduler = DependencyAwareScheduler()

    with pytest.raises(TaskScheduleBudgetError, match="cost budget"):
        scheduler.build(
            ("a", "b"),
            task_profiles=(
                TaskSchedulingProfile(task_id="a", estimated_cost=6.0),
                TaskSchedulingProfile(task_id="b", estimated_cost=6.0),
            ),
            max_project_cost=10.0,
        )


def test_scheduler_rejects_unavailable_provider() -> None:
    scheduler = DependencyAwareScheduler()

    with pytest.raises(TaskScheduleProviderError, match="provider"):
        scheduler.build(
            ("a",),
            task_profiles=(
                TaskSchedulingProfile(
                    task_id="a",
                    provider_available=False,
                ),
            ),
        )


def test_scheduler_rejects_duplicate_profiles() -> None:
    scheduler = DependencyAwareScheduler()

    with pytest.raises(TaskScheduleError, match="multiple scheduling profiles"):
        scheduler.build(
            ("a",),
            task_profiles=(
                TaskSchedulingProfile(task_id="a"),
                TaskSchedulingProfile(task_id="a", priority=1),
            ),
        )


def test_scheduler_rejects_negative_expected_duration() -> None:
    scheduler = DependencyAwareScheduler()

    with pytest.raises(TaskScheduleError, match="negative expected duration"):
        scheduler.build(
            ("a",),
            task_profiles=(
                TaskSchedulingProfile(
                    task_id="a",
                    expected_duration_ms=-1,
                ),
            ),
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
