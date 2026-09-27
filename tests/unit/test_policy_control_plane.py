import pytest
from pydantic import ValidationError

from titan.runtime.policy_store import PolicyDefinition, PolicyVersionStore


def test_policy_definition_has_safe_defaults() -> None:
    definition = PolicyDefinition()

    assert definition.max_task_risk == "R1"
    assert definition.minimum_quality_tier == 1
    assert definition.max_model_cost == 0.0
    assert definition.recovery_enabled is False
    assert definition.recovery_max_attempts == 2
    assert definition.recovery_min_autonomy_level == 3


def test_policy_definition_rejects_invalid_risk() -> None:
    with pytest.raises(ValidationError):
        PolicyDefinition(max_task_risk="R9")


def test_policy_definition_rejects_negative_budget() -> None:
    with pytest.raises(ValidationError):
        PolicyDefinition(max_model_cost=-1.0)


def test_policy_store_is_importable() -> None:
    assert PolicyVersionStore is not None


@pytest.mark.asyncio
async def test_policy_store_rejects_invalid_scopes_without_database_access() -> None:
    store = PolicyVersionStore()

    with pytest.raises(ValueError, match="Global policies"):
        await store.create(
            None,
            policy_name="default",
            scope_type="GLOBAL",
            scope_id="00000000-0000-0000-0000-000000000000",
        )

    with pytest.raises(ValueError, match="require a scope id"):
        await store.create(
            None,
            policy_name="project-policy",
            scope_type="PROJECT",
        )


def test_policy_api_contracts_import_cleanly() -> None:
    from titan.api.app import (
        GovernanceDecisionResponse,
        PolicyCreateRequest,
        PolicyVersionResponse,
    )

    request = PolicyCreateRequest(policy_name="execution")
    assert request.scope_type == "GLOBAL"
    assert PolicyVersionResponse is not None
    assert GovernanceDecisionResponse is not None
