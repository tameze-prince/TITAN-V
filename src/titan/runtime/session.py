from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.config import settings
from titan.persistence.models import (
    OidcAuthorizationStateModel,
    OperatorSessionModel,
    OperatorUserModel,
)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_session_token() -> str:
    return secrets.token_urlsafe(48)


def new_state_token() -> str:
    return secrets.token_urlsafe(32)


def new_code_verifier() -> str:
    return secrets.token_urlsafe(64)


def new_nonce() -> str:
    return secrets.token_urlsafe(32)


def code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


async def create_oidc_authorization_state(
    session: AsyncSession,
    *,
    state: str,
    code_verifier: str,
    nonce: str,
    redirect_uri: str,
) -> OidcAuthorizationStateModel:
    now = datetime.now(UTC)
    row = OidcAuthorizationStateModel(
        state_hash=sha256(state),
        code_verifier=code_verifier,
        nonce=nonce,
        redirect_uri=redirect_uri,
        expires_at=now + timedelta(
            seconds=max(60, settings.oidc_auth_state_ttl_seconds)
        ),
    )
    session.add(row)
    await session.flush()
    return row


async def consume_oidc_authorization_state(
    session: AsyncSession,
    *,
    state: str,
) -> OidcAuthorizationStateModel:
    now = datetime.now(UTC)
    row = await session.scalar(
        select(OidcAuthorizationStateModel)
        .where(OidcAuthorizationStateModel.state_hash == sha256(state))
        .with_for_update()
    )
    if row is None or row.used_at is not None or row.expires_at <= now:
        raise ValueError("Invalid or expired OIDC authorization state")

    row.used_at = now
    return row


async def upsert_operator_user(
    session: AsyncSession,
    *,
    issuer: str,
    subject: str,
    role: str,
    email: str | None,
    display_name: str | None,
) -> OperatorUserModel:
    row = await session.scalar(
        select(OperatorUserModel)
        .where(
            OperatorUserModel.issuer == issuer,
            OperatorUserModel.subject == subject,
        )
        .with_for_update()
    )
    now = datetime.now(UTC)

    if row is None:
        row = OperatorUserModel(
            issuer=issuer,
            subject=subject,
            role=role,
            email=email,
            display_name=display_name,
            last_login_at=now,
        )
        session.add(row)
        await session.flush()
        return row

    row.role = role
    row.email = email
    row.display_name = display_name
    row.status = "ACTIVE"
    row.last_login_at = now
    return row


async def create_operator_session(
    session: AsyncSession,
    *,
    user: OperatorUserModel,
    rotated_from_session_id=None,
) -> tuple[OperatorSessionModel, str]:
    raw_token = new_session_token()
    now = datetime.now(UTC)
    row = OperatorSessionModel(
        user_id=user.id,
        token_hash=sha256(raw_token),
        expires_at=now + timedelta(
            seconds=max(300, settings.operator_session_ttl_seconds)
        ),
        rotated_from_session_id=rotated_from_session_id,
    )
    session.add(row)
    await session.flush()
    return row, raw_token


async def resolve_operator_session(
    session: AsyncSession,
    *,
    raw_token: str,
) -> tuple[OperatorSessionModel, OperatorUserModel] | None:
    now = datetime.now(UTC)
    row = await session.scalar(
        select(OperatorSessionModel)
        .where(OperatorSessionModel.token_hash == sha256(raw_token))
        .with_for_update()
    )
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        return None

    user = await session.scalar(
        select(OperatorUserModel).where(OperatorUserModel.id == row.user_id)
    )
    if user is None or user.status != "ACTIVE":
        return None

    row.last_seen_at = now
    return row, user


async def revoke_operator_session(
    session: AsyncSession,
    *,
    raw_token: str,
) -> bool:
    row = await session.scalar(
        select(OperatorSessionModel).where(
            OperatorSessionModel.token_hash == sha256(raw_token)
        )
    )
    if row is None or row.revoked_at is not None:
        return False

    row.revoked_at = datetime.now(UTC)
    return True


def oidc_authorization_url(
    *,
    state: str,
    nonce: str,
    code_verifier: str,
    redirect_uri: str,
) -> str:
    endpoint = settings.oidc_authorization_endpoint
    client_id = settings.oidc_client_id

    if not endpoint or not client_id:
        raise ValueError("OIDC browser authorization is not configured")

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": settings.oidc_scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge(code_verifier),
        "code_challenge_method": "S256",
    }
    return endpoint + ("&" if "?" in endpoint else "?") + urlencode(params)
