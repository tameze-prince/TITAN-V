from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import pytest
from starlette.requests import Request

from titan.config import settings
from titan.runtime.operator_auth import require_operator, resolve_oidc_identity
from titan.runtime.session import code_challenge, new_code_verifier, oidc_authorization_url


@pytest.mark.asyncio
async def test_development_operator_identity_does_not_require_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "operator_auth_required", False)
    monkeypatch.setattr(settings, "operator_subject", "test-operator")
    monkeypatch.setattr(settings, "operator_role", "operator")

    identity = await require_operator(
        request=None,
        credentials=None,
    )

    assert identity.subject == "test-operator"
    assert identity.role == "operator"


@pytest.mark.asyncio
async def test_production_operator_requires_valid_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_auth_required", True)
    monkeypatch.setattr(settings, "operator_auth_mode", "static")
    monkeypatch.setattr(settings, "operator_api_token", "secret-token")
    monkeypatch.setattr(settings, "operator_subject", "prod-operator")
    monkeypatch.setattr(settings, "operator_role", "admin")

    with pytest.raises(HTTPException) as missing:
        await require_operator(request=None, credentials=None)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as invalid:
        await require_operator(
            request=None,
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="wrong-token",
            ),
        )
    assert invalid.value.status_code == 401

    identity = await require_operator(
        request=None,
        credentials=HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="secret-token",
        ),
    )

    assert identity.subject == "prod-operator"
    assert identity.role == "admin"


@pytest.mark.asyncio
async def test_operator_permissions_are_role_scoped(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_auth_required", True)
    monkeypatch.setattr(settings, "operator_auth_mode", "static")
    monkeypatch.setattr(settings, "operator_api_token", "viewer-token")
    monkeypatch.setattr(settings, "operator_subject", "viewer")
    monkeypatch.setattr(settings, "operator_role", "viewer")

    identity = await require_operator(
        request=None,
        credentials=HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="viewer-token",
        ),
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


@pytest.mark.asyncio
async def test_oidc_mode_rejects_missing_configuration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_auth_required", True)
    monkeypatch.setattr(settings, "operator_auth_mode", "oidc")
    monkeypatch.setattr(settings, "oidc_issuer_url", None)
    monkeypatch.setattr(settings, "oidc_audience", None)
    monkeypatch.setattr(settings, "oidc_jwks_url", None)

    with pytest.raises(HTTPException) as rejected:
        await require_operator(
            request=None,
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="oidc-token",
            ),
        )

    assert rejected.value.status_code == 503


@pytest.mark.asyncio
async def test_oidc_mode_rejects_non_https_configuration_when_required(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_auth_required", True)
    monkeypatch.setattr(settings, "operator_auth_mode", "oidc")
    monkeypatch.setattr(settings, "oidc_issuer_url", "http://issuer.example")
    monkeypatch.setattr(settings, "oidc_audience", "titan-api")
    monkeypatch.setattr(settings, "oidc_jwks_url", "http://issuer.example/jwks.json")
    monkeypatch.setattr(settings, "oidc_require_https", True)

    with pytest.raises(HTTPException) as rejected:
        await require_operator(
            request=None,
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="oidc-token",
            ),
        )

    assert rejected.value.status_code == 503


@pytest.mark.asyncio
async def test_unknown_operator_auth_mode_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_auth_required", True)
    monkeypatch.setattr(settings, "operator_auth_mode", "unknown")

    with pytest.raises(HTTPException) as rejected:
        await require_operator(
            request=None,
            credentials=HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials="token",
            ),
        )

    assert rejected.value.status_code == 503


def test_pkce_code_challenge_uses_s256() -> None:
    verifier = new_code_verifier()
    challenge = code_challenge(verifier)

    assert verifier
    assert challenge
    assert challenge != verifier


def test_oidc_authorization_url_contains_pkce_and_state(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "oidc_authorization_endpoint",
        "https://issuer.example/oauth2/authorize",
    )
    monkeypatch.setattr(settings, "oidc_client_id", "titan-web")
    url = oidc_authorization_url(
        state="state-123",
        nonce="nonce-456",
        code_verifier="verifier-789",
        redirect_uri="https://titan.example/api/auth/callback",
    )

    assert "response_type=code" in url
    assert "code_challenge_method=S256" in url
    assert "state=state-123" in url
    assert "nonce=nonce-456" in url


@pytest.mark.asyncio
async def test_oidc_session_cookie_path_returns_session_identity(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "operator_auth_required", True)
    monkeypatch.setattr(settings, "operator_auth_mode", "oidc")

    from titan.runtime import operator_auth

    async def fake_session_identity(_request):
        return operator_auth.OperatorIdentity(
            subject="session-user",
            role="operator",
            auth_method="session",
            issuer="https://issuer.example",
        )

    monkeypatch.setattr(
        operator_auth,
        "_authenticate_session_cookie",
        fake_session_identity,
    )

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auth/session",
            "headers": [],
            "query_string": b"",
        }
    )
    identity = await require_operator(request=request, credentials=None)

    assert identity.subject == "session-user"
    assert identity.auth_method == "session"
