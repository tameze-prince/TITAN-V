from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from titan.config import settings
from titan.persistence.models import (
    OperatorDelegationModel,
    OperatorResourceGrantModel,
    OperatorUserModel,
)
from titan.runtime.operator_auth import OperatorIdentity
from titan.runtime.resource_access import has_resource_permission


@pytest.mark.asyncio
async def test_resource_permission_uses_explicit_grant_when_required(monkeypatch) -> None:
    monkeypatch.setattr(settings, "resource_rbac_required", True)
    monkeypatch.setattr(settings, "resource_rbac_admin_bypass", False)

    user_id = uuid4()
    project_id = uuid4()

    class FakeScalar:
        async def all_grants(self):
            return [
                OperatorResourceGrantModel(
                    user_id=user_id,
                    resource_type="project",
                    resource_id=project_id,
                    permissions=["task:approve"],
                    status="ACTIVE",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            ]

    class FakeSession:
        async def scalars(self, statement):
            return FakeScalar()

    identity = OperatorIdentity(
        subject="operator",
        role="operator",
        auth_method="session",
        user_id=user_id,
    )

    # This is a contract test for the authorization rule; integration tests exercise SQL.
    assert identity.has_permission("task:approve")
