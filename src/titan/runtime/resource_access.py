from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.config import settings
from titan.persistence.models import (
    OperatorDelegationModel,
    OperatorResourceGrantModel,
)
from titan.runtime.operator_auth import OperatorIdentity


ROLE_ORDER = {"viewer": 0, "operator": 1, "admin": 2}


def role_at_least(actual: str, required: str) -> bool:
    return ROLE_ORDER.get(actual, -1) >= ROLE_ORDER.get(required, 99)


async def has_resource_permission(
    session: AsyncSession,
    *,
    operator: OperatorIdentity,
    permission: str,
    resource_type: str,
    resource_id: UUID | None,
) -> bool:
    if operator.has_permission(permission) and not settings.resource_rbac_required:
        return True

    if (
        settings.resource_rbac_admin_bypass
        and operator.role == "admin"
        and operator.has_permission(permission)
    ):
        return True

    if operator.user_id is None:
        return operator.has_permission(permission)

    now = datetime.now(UTC)

    grants = list(
        await session.scalars(
            select(OperatorResourceGrantModel).where(
                OperatorResourceGrantModel.user_id == operator.user_id,
                OperatorResourceGrantModel.resource_type == resource_type,
                OperatorResourceGrantModel.status == "ACTIVE",
            )
        )
    )
    for grant in grants:
        if grant.expires_at is not None and grant.expires_at <= now:
            continue
        if grant.resource_id not in {None, resource_id}:
            continue
        if permission in set(grant.permissions):
            return True

    delegations = list(
        await session.scalars(
            select(OperatorDelegationModel).where(
                OperatorDelegationModel.delegatee_user_id == operator.user_id,
                OperatorDelegationModel.resource_type == resource_type,
                OperatorDelegationModel.status == "ACTIVE",
                OperatorDelegationModel.revoked_at.is_(None),
                OperatorDelegationModel.starts_at <= now,
                OperatorDelegationModel.expires_at > now,
            )
        )
    )
    for delegation in delegations:
        if delegation.resource_id not in {None, resource_id}:
            continue
        if permission in set(delegation.permissions):
            return True

    return False


async def require_resource_permission(
    session: AsyncSession,
    *,
    operator: OperatorIdentity,
    permission: str,
    resource_type: str,
    resource_id: UUID | None,
) -> None:
    if await has_resource_permission(
        session,
        operator=operator,
        permission=permission,
        resource_type=resource_type,
        resource_id=resource_id,
    ):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Operator '{operator.subject}' lacks '{permission}' on "
            f"{resource_type}:{resource_id or '*'}"
        ),
    )


async def can_delegate_permission(
    session: AsyncSession,
    *,
    operator: OperatorIdentity,
    permission: str,
    resource_type: str,
    resource_id: UUID | None,
) -> bool:
    return await has_resource_permission(
        session,
        operator=operator,
        permission=permission,
        resource_type=resource_type,
        resource_id=resource_id,
    )
