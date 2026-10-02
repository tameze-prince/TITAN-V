from typing import ClassVar


import pytest

from titan.runtime.governance import GovernanceAction, GovernanceEngine
from titan.runtime.model_router import ModelBudget, ModelRoute, ModelSelection
from titan.runtime.policies import PolicyDecision
from titan.runtime.providers import LocalStructuredProvider
from titan.runtime.recovery import RecoveryAssessment


def local_selection(quality_tier: int = 1) -> ModelSelection:
    return ModelSelection(
        route=ModelRoute(
            name="local-test",
            provider="local",
            model="local",
            quality_tier=quality_tier,
        ),
        provider=LocalStructuredProvider(),
    )


def test_governance_allows_runtime_and_model_when_policies_pass() -> None:
    decision = GovernanceEngine.decide_runtime(
        runtime_policy=PolicyDecision(True, "runtime ok"),
        selection=local_selection(),
        minimum_quality_tier=1,
        budget=ModelBudget(),
    )

    assert decision.action is GovernanceAction.ALLOW
    assert decision.allowed is True
    assert decision.requires_human is False


def test_governance_denies_when_runtime_policy_fails() -> None:
    decision = GovernanceEngine.decide_runtime(
        runtime_policy=PolicyDecision(False, "risk denied"),
        selection=local_selection(),
        minimum_quality_tier=1,
        budget=ModelBudget(),
    )

    assert decision.action is GovernanceAction.DENY
    assert decision.allowed is False
    assert "risk denied" in decision.reason


def test_governance_denies_when_model_quality_is_insufficient() -> None:
    check = GovernanceEngine.check_model(
        selection=local_selection(quality_tier=1),
        minimum_quality_tier=2,
        budget=ModelBudget(),
    )

    decision = GovernanceEngine.decide((check,))

    assert decision.action is GovernanceAction.DENY
    assert "below required tier" in decision.reason


def test_governance_requires_human_for_escalated_recovery() -> None:
    assessment = RecoveryAssessment(
        action="ESCALATE",
        reason="Recovery requires approval",
        next_attempt=1,
        max_attempts=2,
    )

    check = GovernanceEngine.check_recovery(assessment)
    decision = GovernanceEngine.decide((check,))

    assert decision.action is GovernanceAction.APPROVAL_REQUIRED
    assert decision.requires_human is True


def test_governance_allows_human_approved_recovery() -> None:
    assessment = RecoveryAssessment(
        action="ESCALATE",
        reason="Recovery requires approval",
        next_attempt=1,
        max_attempts=2,
    )

    check = GovernanceEngine.check_recovery(
        assessment,
        human_approved=True,
    )
    decision = GovernanceEngine.decide((check,))

    assert decision.action is GovernanceAction.ALLOW
    assert decision.allowed is True


def test_governance_denies_model_budget_before_execution() -> None:
    selection = ModelSelection(
        route=ModelRoute(
            name="expensive",
            provider="local",
            model="local",
            quality_tier=2,
            input_cost_per_1k=10.0,
            output_cost_per_1k=10.0,
        ),
        provider=LocalStructuredProvider(),
    )

    check = GovernanceEngine.check_model(
        selection=selection,
        minimum_quality_tier=2,
        budget=ModelBudget(
            max_input_tokens=1_000,
            max_output_tokens=1_000,
            max_cost=1.0,
        ),
    )
    decision = GovernanceEngine.decide((check,))

    assert decision.action is GovernanceAction.DENY
    assert "exceeds configured budget" in decision.reason


def test_multi_operator_quorum_requires_human_approval() -> None:
    from titan.runtime.governance import task_requires_human_approval

    assert task_requires_human_approval(
        risk_level="R1",
        approval_requirement="NONE",
        approval_quorum=2,
    )


def test_risk_aware_task_approval_gate() -> None:
    from titan.runtime.governance import task_requires_human_approval

    assert not task_requires_human_approval(
        risk_level="R1",
        approval_requirement="NONE",
    )
    assert task_requires_human_approval(
        risk_level="R1",
        approval_requirement="HUMAN",
    )
    assert task_requires_human_approval(
        risk_level="R2",
        approval_requirement="NONE",
    )


def test_policy_definition_supports_task_approval_escalation() -> None:
    from titan.runtime.policy_store import PolicyDefinition

    policy = PolicyDefinition(
        task_approval_quorum=2,
        task_approval_min_role="operator",
        task_approval_escalation_role="admin",
        task_approval_escalation_enabled=True,
        delegation_allowed=True,
        delegation_max_ttl_seconds=3_600,
    )

    assert policy.task_approval_quorum == 2
    assert policy.task_approval_escalation_role == "admin"
    assert policy.delegation_allowed is True


@pytest.mark.asyncio
async def test_task_approval_policy_escalates_role_after_wait(monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from titan.runtime.approval_policy import resolve_task_approval_policy
    from titan.runtime.policy_store import PolicyVersionStore

    task = type(
        "Task",
        (),
        {
            "approval_quorum": 1,
            "updated_at": datetime.now(UTC) - timedelta(seconds=120),
        },
    )()

    class FakePolicy:
        definition_json: ClassVar[dict] = {
            "task_approval_quorum": 2,
            "task_approval_min_role": "operator",
            "task_approval_escalation_role": "admin",
            "task_approval_escalation_enabled": True,
            "task_approval_escalation_after_seconds": 60,
            "delegation_allowed": True,
            "delegation_max_ttl_seconds": 3600,
        }

    async def fake_resolve(self, session, *, policy_name, project_id=None, agent_id=None):
        assert policy_name == "task_approval"
        assert project_id is not None
        return FakePolicy()

    monkeypatch.setattr(PolicyVersionStore, "resolve_effective", fake_resolve)

    policy = await resolve_task_approval_policy(
        None,
        project_id=uuid4(),
        task=task,
    )

    assert policy.quorum == 2
    assert policy.minimum_role == "admin"
    assert policy.delegation_allowed is True
