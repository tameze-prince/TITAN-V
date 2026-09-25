from titan.runtime.recovery import RecoveryPolicy


def test_recovery_policy_allows_bounded_low_risk_auto_recovery() -> None:
    policy = RecoveryPolicy(
        enabled=True,
        max_attempts=2,
        min_autonomy_level=3,
        max_auto_risk_level="R1",
    )

    decision = policy.assess(
        autonomy_level=3,
        current_attempt=0,
        failed_risk_levels=("R1",),
        approval_required=False,
    )

    assert decision.action == "AUTO_RECOVER"
    assert decision.next_attempt == 1


def test_recovery_policy_escalates_high_risk_work() -> None:
    policy = RecoveryPolicy(enabled=True)

    decision = policy.assess(
        autonomy_level=5,
        current_attempt=0,
        failed_risk_levels=("R2",),
        approval_required=False,
    )

    assert decision.action == "ESCALATE"
    assert "risk ceiling" in decision.reason


def test_recovery_policy_escalates_when_approval_is_required() -> None:
    policy = RecoveryPolicy(enabled=True)

    decision = policy.assess(
        autonomy_level=5,
        current_attempt=0,
        failed_risk_levels=("R1",),
        approval_required=True,
    )

    assert decision.action == "ESCALATE"
    assert "human approval" in decision.reason


def test_recovery_policy_stops_after_attempt_budget() -> None:
    policy = RecoveryPolicy(enabled=True, max_attempts=2)

    decision = policy.assess(
        autonomy_level=5,
        current_attempt=2,
        failed_risk_levels=("R1",),
        approval_required=False,
    )

    assert decision.action == "ESCALATE"
    assert "budget exhausted" in decision.reason
