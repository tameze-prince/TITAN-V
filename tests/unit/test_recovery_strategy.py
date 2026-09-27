from titan.runtime.recovery_strategy import (
    FailureCategory,
    RecoveryObservation,
    observations_from_events,
    RecoveryStrategy,
    RecoveryStrategySelector,
    classify_failure,
)


def test_failure_classification_is_deterministic() -> None:
    assert classify_failure("provider rate limit exceeded") == FailureCategory.PROVIDER
    assert classify_failure("model token budget exceeded") == FailureCategory.BUDGET
    assert classify_failure("tool sandbox permission denied") == FailureCategory.TOOL
    assert classify_failure("dependency task is blocked") == FailureCategory.DEPENDENCY
    assert classify_failure("quality evaluation failed") == FailureCategory.EVALUATION
    assert classify_failure("unexpected database outage") == FailureCategory.UNKNOWN


def test_selector_defaults_to_reassignment_without_history() -> None:
    selection = RecoveryStrategySelector().select(
        category=FailureCategory.PROVIDER,
        observations=(),
    )

    assert selection.strategy == RecoveryStrategy.REPLAN_REASSIGN


def test_selector_switches_strategy_after_repeated_failure() -> None:
    observations = (
        RecoveryObservation(
            category=FailureCategory.PROVIDER,
            strategy=RecoveryStrategy.REPLAN_REASSIGN,
            outcome="REPEATED_FAILURE",
        ),
    )

    selection = RecoveryStrategySelector().select(
        category=FailureCategory.PROVIDER,
        observations=observations,
    )

    assert selection.strategy == RecoveryStrategy.REPLAN_SAME_AGENT


def test_selector_rewards_resolved_strategy() -> None:
    observations = (
        RecoveryObservation(
            category=FailureCategory.EVALUATION,
            strategy=RecoveryStrategy.REPLAN_REASSIGN,
            outcome="RESOLVED",
        ),
        RecoveryObservation(
            category=FailureCategory.EVALUATION,
            strategy=RecoveryStrategy.REPLAN_SAME_AGENT,
            outcome="REPEATED_FAILURE",
        ),
    )

    selection = RecoveryStrategySelector().select(
        category=FailureCategory.EVALUATION,
        observations=observations,
    )

    assert selection.strategy == RecoveryStrategy.REPLAN_REASSIGN


def test_unrelated_failure_categories_do_not_change_selection() -> None:
    observations = (
        RecoveryObservation(
            category=FailureCategory.PROVIDER,
            strategy=RecoveryStrategy.REPLAN_SAME_AGENT,
            outcome="RESOLVED",
        ),
    )

    selection = RecoveryStrategySelector().select(
        category=FailureCategory.TOOL,
        observations=observations,
    )

    assert selection.strategy == RecoveryStrategy.REPLAN_REASSIGN


def test_selector_penalizes_expensive_and_slow_recovery_strategies() -> None:
    observations = (
        RecoveryObservation(
            category=FailureCategory.TOOL,
            strategy=RecoveryStrategy.REPLAN_REASSIGN,
            outcome="RESOLVED",
            actual_cost=1.0,
            duration_ms=100,
        ),
        RecoveryObservation(
            category=FailureCategory.TOOL,
            strategy=RecoveryStrategy.REPLAN_SAME_AGENT,
            outcome="RESOLVED",
            actual_cost=100.0,
            duration_ms=10_000,
        ),
    )

    selection = RecoveryStrategySelector().select(
        category=FailureCategory.TOOL,
        observations=observations,
    )

    assert selection.strategy == RecoveryStrategy.REPLAN_REASSIGN


def test_observation_event_parser_reads_strategy_cost_and_duration() -> None:
    class Event:
        type = "RecoveryResolved"
        payload = {
            "failure_category": "BUDGET",
            "strategy": "REPLAN_REASSIGN",
            "actual_cost": 1.25,
            "duration_ms": 1200,
        }

    observations = observations_from_events((Event(),))

    assert observations[0].category == FailureCategory.BUDGET
    assert observations[0].strategy == RecoveryStrategy.REPLAN_REASSIGN
    assert observations[0].actual_cost == 1.25
    assert observations[0].duration_ms == 1200
