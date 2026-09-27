import pytest
from pydantic import ValidationError

from titan.api.app import RecoveryDecisionRequest, RecoveryRollbackRequest
from titan.runtime.recovery_service import RecoveryStartResult
from titan.runtime.recovery_strategy import RecoveryStrategy


def test_recovery_decision_request_validates_strategy() -> None:
    request = RecoveryDecisionRequest(
        approved=True,
        strategy=RecoveryStrategy.REPLAN_SAME_AGENT,
        reason="Human-approved retry on the current agent",
    )

    assert request.approved is True
    assert request.strategy == RecoveryStrategy.REPLAN_SAME_AGENT


def test_recovery_decision_request_allows_rejection_without_strategy() -> None:
    request = RecoveryDecisionRequest(
        approved=False,
        reason="Require a different human decision",
    )

    assert request.approved is False
    assert request.strategy is None


def test_recovery_rollback_request_requires_a_reason() -> None:
    with pytest.raises(ValidationError):
        RecoveryRollbackRequest(reason="")

    request = RecoveryRollbackRequest(reason="Recovery produced an invalid result")
    assert request.reason.startswith("Recovery")


def test_recovery_service_result_imports_cleanly() -> None:
    assert RecoveryStartResult.__annotations__["recovery_attempt"] is int
