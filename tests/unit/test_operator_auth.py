from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import pytest

from titan.config import settings
from titan.runtime.operator_auth import require_operator


@pytest.mark.asyncio
async def test_development_operator_identity_does_not_require_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "operator_auth_required", False)
    monkeypatch.setattr(settings, "operator_subject", "test-operator")
    monkeypatch.setattr(settings, "operator_role", "operator")

    identity = await require_operator(None)

    assert identity.subject == "test-operator"
    assert identity.role == "operator"


@pytest.mark.asyncio
async def test_production_operator_requires_valid_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_auth_required", True)
    monkeypatch.setattr(settings, "operator_api_token", "secret-token")
    monkeypatch.setattr(settings, "operator_subject", "prod-operator")
    monkeypatch.setattr(settings, "operator_role", "admin")

    with pytest.raises(HTTPException) as missing:
        await require_operator(None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as invalid:
        await require_operator(
            HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="wrong-token",
            )
        )
    assert invalid.value.status_code == 401

    identity = await require_operator(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="secret-token",
        )
    )

    assert identity.subject == "prod-operator"
    assert identity.role == "admin"
