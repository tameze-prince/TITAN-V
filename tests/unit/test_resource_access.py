import pytest

from titan.config import settings
from titan.runtime.operator_auth import OperatorIdentity
from titan.runtime.resource_access import role_at_least


def test_role_hierarchy_is_monotonic() -> None:
    assert role_at_least("admin", "operator")
    assert role_at_least("operator", "viewer")
    assert not role_at_least("viewer", "operator")


@pytest.mark.asyncio
async def test_global_permission_requires_resource_mode_to_be_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "resource_rbac_required", False)

    identity = OperatorIdentity(
        subject="operator",
        role="operator",
        auth_method="static",
    )

    from titan.runtime.resource_access import has_resource_permission

    assert await has_resource_permission(
        None,
        operator=identity,
        permission="task:approve",
        resource_type="project",
        resource_id=None,
    )


@pytest.mark.asyncio
async def test_resource_mode_fails_closed_without_persistent_user(monkeypatch) -> None:
    monkeypatch.setattr(settings, "resource_rbac_required", True)
    monkeypatch.setattr(settings, "resource_rbac_admin_bypass", False)

    identity = OperatorIdentity(
        subject="operator",
        role="operator",
        auth_method="static",
    )

    from titan.runtime.resource_access import has_resource_permission

    assert not await has_resource_permission(
        None,
        operator=identity,
        permission="task:approve",
        resource_type="project",
        resource_id=None,
    )
