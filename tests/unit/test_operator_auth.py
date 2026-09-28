from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import pytest

from titan.config import settings
from titan.runtime.operator_auth import require_operator, resolve_oidc_identity


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


@pytest.mark.asyncio
async def test_operator_permissions_are_role_scoped(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_auth_required", True)
    monkeypatch.setattr(settings, "operator_api_token", "viewer-token")
    monkeypatch.setattr(settings, "operator_subject", "viewer")
    monkeypatch.setattr(settings, "operator_role", "viewer")

    identity = await require_operator(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="viewer-token",
        )
    )

    assert identity.has_permission("control_plane:read")
    assert not identity.has_permission("recovery:approve")

    with pytest.raises(HTTPException) as denied:
        identity.require_permission("recovery:rollback")
    assert denied.value.status_code == 403

  
def test_oidc_identity_resolves_highest_privileged_allowed_role(monkeypatch) -> None:
    monkeypatch.setattr(settings, "oidc_roles_claim", "roles")
    monkeypatch.setattr(settings, "oidc_admin_roles", "admin")
    monkeypatch.setattr(settings, "oidc_operator_roles", "operator")
    monkeypatch.setattr(settings, "oidc_viewer_roles", "viewer")

    identity = resolve_oidc_identity(
        {
            "iss": "https://issuer.example",
            "sub": "user-42",
            "roles": ["viewer", "operator", "admin"],
        }
    )

    assert identity.subject == "user-42"
    assert identity.role == "admin"
    assert identity.auth_method == "oidc"
    assert identity.issuer == "https://issuer.example"


def test_oidc_identity_rejects_missing_titan_role(monkeypatch) -> None:
    monkeypatch.setattr(settings, "oidc_roles_claim", "roles")
    monkeypatch.setattr(settings, "oidc_admin_roles", "admin")
    monkeypatch.setattr(settings, "oidc_operator_roles", "operator")
    monkeypatch.setattr(settings, "oidc_viewer_roles", "viewer")

    with pytest.raises(HTTPException) as denied:
        resolve_oidc_identity(
            {
                "iss": "https://issuer.example",
                "sub": "user-43",
                "roles": ["guest"],
            }
        )

    assert denied.value.status_code == 403
