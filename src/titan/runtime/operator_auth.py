from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass
from secrets import compare_digest
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from titan.config import settings
from titan.persistence.database import SessionFactory
from titan.runtime.session import resolve_operator_session


_bearer = HTTPBearer(auto_error=False)
_jwks_lock = asyncio.Lock()
_jwks_cache: tuple[float, list[dict[str, Any]]] | None = None

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "viewer": frozenset({"control_plane:read"}),
    "operator": frozenset(
        {
            "control_plane:read",
            "recovery:approve",
            "recovery:rollback",
            "task:approve",
        }
    ),
    "admin": frozenset(
        {
            "control_plane:read",
            "recovery:approve",
            "recovery:rollback",
            "task:approve",
            "policy:admin",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class OperatorIdentity:
    subject: str
    role: str
    auth_method: str = "static"
    issuer: str | None = None
    user_id: uuid.UUID | None = None
    session_id: uuid.UUID | None = None

    def has_permission(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, frozenset())

    def require_permission(self, permission: str) -> None:
        if self.has_permission(permission):
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operator role '{self.role}' lacks permission '{permission}'",
        )


def _split_configured_values(value: str) -> frozenset[str]:
    return frozenset(item.strip() for item in value.split(",") if item.strip())


def _claim_value(claims: dict[str, Any], path: str) -> Any:
    current: Any = claims
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _claim_values(value: Any) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset(item for item in value.split() if item)
    if isinstance(value, (list, tuple, set)):
        return frozenset(str(item) for item in value)
    return frozenset()


def _resolve_oidc_role(claims: dict[str, Any]) -> str:
    values = _claim_values(_claim_value(claims, settings.oidc_roles_claim))
    role_map = (
        ("admin", _split_configured_values(settings.oidc_admin_roles)),
        ("operator", _split_configured_values(settings.oidc_operator_roles)),
        ("viewer", _split_configured_values(settings.oidc_viewer_roles)),
    )
    for role, allowed_values in role_map:
        if values.intersection(allowed_values):
            return role
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="OIDC identity does not carry an allowed TITAN operator role",
    )


def resolve_oidc_identity(claims: dict[str, Any]) -> OperatorIdentity:
    subject = claims.get("sub")
    issuer = claims.get("iss")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token has no valid subject",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not isinstance(issuer, str) or not issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token has no valid issuer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return OperatorIdentity(
        subject=subject,
        role=_resolve_oidc_role(claims),
        auth_method="oidc",
        issuer=issuer,
    )


def _validate_oidc_configuration() -> tuple[str, str, str]:
    issuer = settings.oidc_issuer_url
    audience = settings.oidc_audience
    jwks_url = settings.oidc_jwks_url
    if not issuer or not audience or not jwks_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC authentication is not fully configured",
        )
    if settings.oidc_require_https and any(
        not value.lower().startswith("https://")
        for value in (issuer, jwks_url)
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC issuer and JWKS URLs must use HTTPS",
        )
    return issuer, audience, jwks_url


async def _load_jwks(jwks_url: str) -> list[dict[str, Any]]:
    global _jwks_cache

    now = time.monotonic()
    if _jwks_cache is not None and now < _jwks_cache[0]:
        return _jwks_cache[1]

    async with _jwks_lock:
        now = time.monotonic()
        if _jwks_cache is not None and now < _jwks_cache[0]:
            return _jwks_cache[1]

        timeout = httpx.Timeout(settings.oidc_request_timeout_seconds)
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    jwks_url,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                document = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to retrieve OIDC signing keys",
            ) from exc

        keys = document.get("keys") if isinstance(document, dict) else None
        if not isinstance(keys, list) or not keys:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OIDC JWKS endpoint returned no signing keys",
            )

        _jwks_cache = (
            time.monotonic() + max(30, settings.oidc_jwks_cache_seconds),
            [key for key in keys if isinstance(key, dict)],
        )
        return _jwks_cache[1]



async def _validate_oidc_claims(
    token: str,
    *,
    audience: str,
    verify_scope: bool = True,
) -> dict[str, Any]:
    issuer, _, jwks_url = _validate_oidc_configuration()

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        alg = header.get("alg")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OIDC bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not isinstance(kid, str) or not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token is missing a key id",
            headers={"WWW-Authenticate": "Bearer"},
        )

    keys = await _load_jwks(jwks_url)
    candidate = next((key for key in keys if key.get("kid") == kid), None)
    if candidate is None:
        global _jwks_cache
        _jwks_cache = None
        keys = await _load_jwks(jwks_url)
        candidate = next((key for key in keys if key.get("kid") == kid), None)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC signing key not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_algorithm = candidate.get("alg")
    if not isinstance(key_algorithm, str) or key_algorithm != alg:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token algorithm does not match its trusted signing key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        signing_key = jwt.PyJWK.from_dict(candidate)
        allowed_algorithms = _split_configured_values(
            "RS256,RS384,RS512,ES256,ES384,ES512,EdDSA"
        )
        if key_algorithm not in allowed_algorithms:
            raise ValueError("Unsupported OIDC signing algorithm")
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=[key_algorithm],
            audience=audience,
            issuer=issuer,
            leeway=max(0, settings.oidc_clock_skew_seconds),
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC token validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if verify_scope and settings.oidc_required_scope:
        scope_values = _claim_values(claims.get("scope")) | _claim_values(
            claims.get("scp")
        )
        if settings.oidc_required_scope not in scope_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OIDC token lacks the required TITAN scope",
            )

    return claims


async def authenticate_oidc_token(token: str) -> OperatorIdentity:
    _, audience, _ = _validate_oidc_configuration()
    claims = await _validate_oidc_claims(
        token,
        audience=audience,
        verify_scope=True,
    )
    return resolve_oidc_identity(claims)


async def validate_oidc_id_token(
    token: str,
    *,
    nonce: str,
) -> dict[str, Any]:
    client_id = settings.oidc_client_id
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC client id is not configured",
        )
    claims = await _validate_oidc_claims(
        token,
        audience=client_id,
        verify_scope=False,
    )
    if claims.get("nonce") != nonce:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OIDC nonce validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


async def _authenticate_session_cookie(
    request: Request,
) -> OperatorIdentity | None:
    raw = request.cookies.get(settings.operator_session_cookie_name)
    if not raw:
        return None
    async with SessionFactory() as session:
        resolved = await resolve_operator_session(session, raw_token=raw)
        if resolved is None:
            return None
        session_row, user = resolved
        await session.commit()
    return OperatorIdentity(
        subject=user.subject,
        role=user.role,
        auth_method="session",
        issuer=user.issuer,
        user_id=user.id,
        session_id=session_row.id,
    )


async def require_operator(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> OperatorIdentity:
    if not settings.operator_auth_required and settings.environment == "development":
        return OperatorIdentity(
            subject=settings.operator_subject,
            role=settings.operator_role,
            auth_method="development",
        )

    mode = settings.operator_auth_mode.lower()

    if credentials is not None and credentials.scheme.lower() == "bearer":
        if mode == "oidc":
            return await authenticate_oidc_token(credentials.credentials)

        if mode == "static":
            configured = settings.operator_api_token
            if not configured or not compare_digest(
                credentials.credentials,
                configured,
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid operator credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            identity = OperatorIdentity(
                subject=settings.operator_subject,
                role=settings.operator_role,
                auth_method="static",
            )
            if identity.role not in ROLE_PERMISSIONS:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Unsupported operator role '{identity.role}'",
                )
            return identity

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unsupported operator authentication mode '{settings.operator_auth_mode}'",
        )

    if mode == "oidc":
        session_identity = await _authenticate_session_cookie(request)
        if session_identity is not None:
            return session_identity

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Operator authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
