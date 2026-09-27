from titan.runtime.recovery_strategy import (
    FailureCategory,
    RecoveryObservation,
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
