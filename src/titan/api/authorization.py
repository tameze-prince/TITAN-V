from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.config import settings
from titan.persistence.database import get_session
from titan.persistence.models import (
    EventModel,
    OperatorDelegationModel,
    OperatorResourceGrantModel,
    OperatorUserModel,
)
from titan.runtime.operator_auth import OperatorIdentity, require_operator
from titan.runtime.policy_store import PolicyVersionStore
from titan.runtime.resource_access import can_delegate_permission


router = APIRouter(
    prefix="/api/v1/control-plane",
    tags=["authorization"],
    dependencies=[Depends(require_operator)],
)


class ResourceGrantRequest(BaseModel):
    user_id: UUID
    resource_type: str = Field(min_length=1, max_length=64)
    resource_id: UUID | None = None
    permissions: list[str] = Field(min_length=1, max_length=20)
    expires_at: datetime | None = None


class ResourceGrantResponse(BaseModel):
    id: UUID
    user_id: UUID
    resource_type: str
    resource_id: UUID | None
    permissions: list[str]
    status: str
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class DelegationRequest(BaseModel):
    delegatee_subject: str = Field(min_length=1, max_length=255)
    delegatee_issuer: str | None = Field(default=None, max_length=500)
    resource_type: str = Field(min_length=1, max_length=64)
    resource_id: UUID | None = None
    permissions: list[str] = Field(min_length=1, max_length=20)
    expires_at: datetime


class DelegationResponse(BaseModel):
    id: UUID
    delegator_user_id: UUID
    delegatee_user_id: UUID
    resource_type: str
    resource_id: UUID | None
    permissions: list[str]
    status: str
    starts_at: datetime
    expires_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


@router.post(
    "/projects/{project_id}/authorization/grants",
    response_model=ResourceGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resource_grant(
    project_id: UUID,
    payload: ResourceGrantRequest,
    session: AsyncSession = Depends(get_session),
    operator: OperatorIdentity = Depends(require_operator),
) -> ResourceGrantResponse:
    operator.require_permission("policy:admin")

    if payload.expires_at is not None and payload.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Grant expiry must be in the future")

    user = await session.scalar(
        select(OperatorUserModel).where(OperatorUserModel.id == payload.user_id)
    )
    if user is None or user.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Operator user not found")

    grant = OperatorResourceGrantModel(
        user_id=user.id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id or project_id if payload.resource_type == "project" else payload.resource_id,
        permissions=sorted(set(payload.permissions)),
        expires_at=payload.expires_at,
        granted_by_subject=operator.subject,
    )
    session.add(grant)
    session.add(
        EventModel(
            project_id=project_id,
            type="OperatorResourceGrantCreated",
            actor_type="OPERATOR",
            actor_subject=operator.subject,
            aggregate_type="OPERATOR_GRANT",
            aggregate_id=grant.id,
            payload={
                "user_id": str(user.id),
                "resource_type": payload.resource_type,
                "resource_id": str(grant.resource_id) if grant.resource_id else None,
                "permissions": grant.permissions,
                "expires_at": payload.expires_at.isoformat() if payload.expires_at else None,
            },
        )
    )
    await session.commit()
    await session.refresh(grant)
    return ResourceGrantResponse.model_validate(grant)


@router.post(
    "/projects/{project_id}/authorization/delegations",
    response_model=DelegationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_delegation(
    project_id: UUID,
    payload: DelegationRequest,
    session: AsyncSession = Depends(get_session),
    operator: OperatorIdentity = Depends(require_operator),
) -> DelegationResponse:
    if not operator.has_permission("task:approve"):
        raise HTTPException(status_code=403, detail="Operator cannot delegate governed approval authority")

    policy = await PolicyVersionStore().resolve_effective(
        session,
        policy_name="task_approval",
        project_id=project_id,
    )
    delegation_allowed = False
    max_ttl = settings.delegation_max_ttl_seconds
    if policy is not None:
        delegation_allowed = bool(policy.definition_json.get("delegation_allowed", False))
        max_ttl = min(
            max_ttl,
            int(policy.definition_json.get("delegation_max_ttl_seconds", max_ttl)),
        )
    if not delegation_allowed:
        raise HTTPException(
            status_code=403,
            detail="Delegation is not enabled by the effective project policy",
        )

    now = datetime.now(UTC)
    if payload.expires_at <= now:
        raise HTTPException(status_code=422, detail="Delegation expiry must be in the future")
    if payload.expires_at > now + timedelta(seconds=max(60, max_ttl)):
        raise HTTPException(
            status_code=422,
            detail="Delegation exceeds the configured maximum lifetime",
        )

    issuer = payload.delegatee_issuer or operator.issuer
    delegatee = await session.scalar(
        select(OperatorUserModel).where(
            OperatorUserModel.subject == payload.delegatee_subject,
            OperatorUserModel.issuer == issuer,
            OperatorUserModel.status == "ACTIVE",
        )
    )
    if delegatee is None:
        raise HTTPException(status_code=404, detail="Delegatee operator user not found")
    if operator.user_id == delegatee.id:
        raise HTTPException(status_code=422, detail="An operator cannot delegate to themself")
    if operator.user_id is None:
        raise HTTPException(status_code=409, detail="Delegation requires a persistent operator session")

    for permission in sorted(set(payload.permissions)):
        if not await can_delegate_permission(
            session,
            operator=operator,
            permission=permission,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id or project_id if payload.resource_type == "project" else payload.resource_id,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Operator cannot delegate permission '{permission}' for this resource",
            )

    delegation = OperatorDelegationModel(
        delegator_user_id=operator.user_id,
        delegatee_user_id=delegatee.id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id or project_id if payload.resource_type == "project" else payload.resource_id,
        permissions=sorted(set(payload.permissions)),
        starts_at=now,
        expires_at=payload.expires_at,
        created_by_subject=operator.subject,
    )
    session.add(delegation)
    session.add(
        EventModel(
            project_id=project_id,
            type="OperatorDelegationCreated",
            actor_type="OPERATOR",
            actor_subject=operator.subject,
            aggregate_type="OPERATOR_DELEGATION",
            aggregate_id=delegation.id,
            payload={
                "delegatee_subject": delegatee.subject,
                "resource_type": delegation.resource_type,
                "resource_id": str(delegation.resource_id) if delegation.resource_id else None,
                "permissions": delegation.permissions,
                "expires_at": delegation.expires_at.isoformat(),
            },
        )
    )
    await session.commit()
    await session.refresh(delegation)
    return DelegationResponse.model_validate(delegation)


@router.post(
    "/projects/{project_id}/authorization/delegations/{delegation_id}/revoke",
    response_model=DelegationResponse,
)
async def revoke_delegation(
    project_id: UUID,
    delegation_id: UUID,
    session: AsyncSession = Depends(get_session),
    operator: OperatorIdentity = Depends(require_operator),
) -> DelegationResponse:
    delegation = await session.scalar(
        select(OperatorDelegationModel)
        .where(OperatorDelegationModel.id == delegation_id)
        .with_for_update()
    )
    if delegation is None:
        raise HTTPException(status_code=404, detail="Delegation not found")

    if delegation.created_by_subject != operator.subject and not operator.has_permission("policy:admin"):
        raise HTTPException(status_code=403, detail="Only the delegator or an administrator can revoke this delegation")

    if delegation.revoked_at is None:
        delegation.revoked_at = datetime.now(UTC)
        delegation.status = "REVOKED"
        session.add(
            EventModel(
                project_id=project_id,
                type="OperatorDelegationRevoked",
                actor_type="OPERATOR",
                actor_subject=operator.subject,
                aggregate_type="OPERATOR_DELEGATION",
                aggregate_id=delegation.id,
                payload={
                    "delegation_id": str(delegation.id),
                    "created_by_subject": delegation.created_by_subject,
                },
            )
        )
        await session.commit()

    await session.refresh(delegation)
    return DelegationResponse.model_validate(delegation)
