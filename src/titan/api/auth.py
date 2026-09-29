from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.config import settings
from titan.persistence.database import SessionFactory
from titan.persistence.models import EventModel, OperatorSessionModel, OperatorUserModel
from titan.persistence.database import get_session
from titan.runtime.operator_auth import OperatorIdentity, require_operator, resolve_oidc_identity, validate_oidc_id_token
from titan.runtime.session import (
    consume_oidc_authorization_state,
    create_oidc_authorization_state,
    create_operator_session,
    new_code_verifier,
    new_nonce,
    new_state_token,
    oidc_authorization_url,
    revoke_operator_session,
    sha256,
    upsert_operator_user,
)


router = APIRouter(prefix='/api/v1/auth', tags=['authentication'])


class OidcCallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=10_000)
    state: str = Field(min_length=1, max_length=512)


class SessionResponse(BaseModel):
    authenticated: bool
    subject: str
    role: str
    issuer: str | None
    auth_method: str
    user_id: str | None
    session_id: str | None
    email: str | None = None
    display_name: str | None = None
    expires_at: str | None = None


def _require_oidc_browser_config() -> tuple[str, str, str]:
    authorization_endpoint = settings.oidc_authorization_endpoint
    token_endpoint = settings.oidc_token_endpoint
    redirect_uri = settings.oidc_redirect_uri
    if not authorization_endpoint or not token_endpoint or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='OIDC browser session is not fully configured',
        )
    if not settings.oidc_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='OIDC client id is not configured',
        )
    if settings.oidc_require_https:
        parsed_urls = [urlparse(value) for value in (authorization_endpoint, token_endpoint)]
        if any(parsed.scheme.lower() != 'https' for parsed in parsed_urls):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail='OIDC authorization and token endpoints must use HTTPS',
            )
    return authorization_endpoint, token_endpoint, redirect_uri


def _cookie_kwargs() -> dict:
    return {
        'key': settings.operator_session_cookie_name,
        'httponly': True,
        'secure': settings.operator_session_cookie_secure,
        'samesite': settings.operator_session_cookie_samesite,
        'path': '/',
        'max_age': max(300, settings.operator_session_ttl_seconds),
    }


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.operator_session_cookie_name,
        path='/',
    )


@router.get('/oidc/start', response_class=RedirectResponse)
async def oidc_start(
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    if settings.operator_auth_mode.lower() != 'oidc':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='OIDC authentication mode is not enabled',
        )

    _, _, redirect_uri = _require_oidc_browser_config()
    state = new_state_token()
    verifier = new_code_verifier()
    nonce = new_nonce()
    await create_oidc_authorization_state(
        session,
        state=state,
        code_verifier=verifier,
        nonce=nonce,
        redirect_uri=redirect_uri,
    )
    await session.commit()

    try:
        target = oidc_authorization_url(
            state=state,
            nonce=nonce,
            code_verifier=verifier,
            redirect_uri=redirect_uri,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)


@router.post('/oidc/callback', response_model=SessionResponse)
async def oidc_callback(
    payload: OidcCallbackRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    _, token_endpoint, _ = _require_oidc_browser_config()

    try:
        auth_state = await consume_oidc_authorization_state(
            session,
            state=payload.state,
        )
        await session.flush()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid or expired OIDC authorization state',
        ) from exc

    form = {
        'grant_type': 'authorization_code',
        'client_id': settings.oidc_client_id or '',
        'code': payload.code,
        'redirect_uri': auth_state.redirect_uri,
        'code_verifier': auth_state.code_verifier,
    }
    if settings.oidc_client_secret:
        form['client_secret'] = settings.oidc_client_secret

    try:
        timeout = httpx.Timeout(settings.oidc_request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            token_response = await client.post(
                token_endpoint,
                data=form,
                headers={'Accept': 'application/json'},
            )
            token_response.raise_for_status()
            token_document = token_response.json()
    except (httpx.HTTPError, ValueError) as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='OIDC token exchange failed',
        ) from exc

    id_token = token_document.get('id_token')
    if not isinstance(id_token, str) or not id_token:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='OIDC provider did not return an id_token',
        )

    claims = await validate_oidc_id_token(
        id_token,
        nonce=auth_state.nonce,
    )
    identity = resolve_oidc_identity(claims)
    user = await upsert_operator_user(
        session,
        issuer=identity.issuer or '',
        subject=identity.subject,
        role=identity.role,
        email=claims.get('email') if isinstance(claims.get('email'), str) else None,
        display_name=(
            claims.get('name')
            if isinstance(claims.get('name'), str)
            else None
        ),
    )
    operator_session, raw_session_token = await create_operator_session(
        session,
        user=user,
    )
    session.add(
        EventModel(
            project_id=None,
            type='OperatorSessionCreated',
            actor_type='OPERATOR',
            actor_subject=user.subject,
            aggregate_type='OPERATOR_SESSION',
            aggregate_id=operator_session.id,
            payload={
                'user_id': str(user.id),
                'role': user.role,
                'auth_method': 'oidc',
                'issuer': user.issuer,
            },
        )
    )
    await session.commit()

    response.set_cookie(value=raw_session_token, **_cookie_kwargs())
    return SessionResponse(
        authenticated=True,
        subject=user.subject,
        role=user.role,
        issuer=user.issuer,
        auth_method='session',
        user_id=str(user.id),
        session_id=str(operator_session.id),
        email=user.email,
        display_name=user.display_name,
        expires_at=operator_session.expires_at.isoformat(),
    )


@router.get('/session', response_model=SessionResponse)
async def get_session_identity(
    operator: OperatorIdentity = Depends(require_operator),
) -> SessionResponse:
    if operator.auth_method == 'development':
        return SessionResponse(
            authenticated=True,
            subject=operator.subject,
            role=operator.role,
            issuer=operator.issuer,
            auth_method=operator.auth_method,
            user_id=str(operator.user_id) if operator.user_id else None,
            session_id=str(operator.session_id) if operator.session_id else None,
        )

    async with SessionFactory() as session:
        user = None
        expires_at = None
        if operator.user_id is not None:
            user = await session.scalar(
                select(OperatorUserModel).where(OperatorUserModel.id == operator.user_id)
            )
        if operator.session_id is not None:
            session_row = await session.scalar(
                select(OperatorSessionModel).where(
                    OperatorSessionModel.id == operator.session_id
                )
            )
            expires_at = session_row.expires_at.isoformat() if session_row else None

    return SessionResponse(
        authenticated=True,
        subject=operator.subject,
        role=operator.role,
        issuer=operator.issuer,
        auth_method=operator.auth_method,
        user_id=str(operator.user_id) if operator.user_id else None,
        session_id=str(operator.session_id) if operator.session_id else None,
        email=user.email if user else None,
        display_name=user.display_name if user else None,
        expires_at=expires_at,
    )


@router.post('/session/rotate', response_model=SessionResponse)
async def rotate_session(
    request: Request,
    response: Response,
    operator: OperatorIdentity = Depends(require_operator),
) -> SessionResponse:
    raw = request.cookies.get(settings.operator_session_cookie_name)
    if not raw or operator.session_id is None or operator.user_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Active browser session required')

    async with SessionFactory() as session:
        current = await session.scalar(
            select(OperatorSessionModel)
            .where(OperatorSessionModel.id == operator.session_id)
            .with_for_update()
        )
        user = await session.scalar(
            select(OperatorUserModel).where(OperatorUserModel.id == operator.user_id)
        )
        if current is None or user is None or current.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Session is no longer active')

        now = datetime.now(UTC)
        age = (now - current.created_at).total_seconds()
        if age < max(60, settings.operator_session_rotation_seconds):
            return SessionResponse(
                authenticated=True,
                subject=user.subject,
                role=user.role,
                issuer=user.issuer,
                auth_method='session',
                user_id=str(user.id),
                session_id=str(current.id),
                email=user.email,
                display_name=user.display_name,
                expires_at=current.expires_at.isoformat(),
            )

        current.revoked_at = now
        replacement, raw_replacement = await create_operator_session(
            session,
            user=user,
            rotated_from_session_id=current.id,
        )
        session.add(
            EventModel(
                project_id=None,
                type='OperatorSessionRotated',
                actor_type='OPERATOR',
                actor_subject=user.subject,
                aggregate_type='OPERATOR_SESSION',
                aggregate_id=replacement.id,
                payload={
                    'user_id': str(user.id),
                    'rotated_from_session_id': str(current.id),
                },
            )
        )
        await session.commit()

    response.set_cookie(value=raw_replacement, **_cookie_kwargs())
    return SessionResponse(
        authenticated=True,
        subject=user.subject,
        role=user.role,
        issuer=user.issuer,
        auth_method='session',
        user_id=str(user.id),
        session_id=str(replacement.id),
        email=user.email,
        display_name=user.display_name,
        expires_at=replacement.expires_at.isoformat(),
    )


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
) -> Response:
    raw = request.cookies.get(settings.operator_session_cookie_name)
    if raw:
        async with SessionFactory() as session:
            row = await session.scalar(
                select(OperatorSessionModel).where(
                    OperatorSessionModel.token_hash == sha256(raw)
                )
            )
            if row is not None and row.revoked_at is None:
                row.revoked_at = datetime.now(UTC)
                session.add(
                    EventModel(
                        project_id=None,
                        type='OperatorSessionRevoked',
                        actor_type='OPERATOR',
                        actor_subject=None,
                        aggregate_type='OPERATOR_SESSION',
                        aggregate_id=row.id,
                        payload={},
                    )
                )
                await session.commit()
    _clear_cookie(response)
    return response
