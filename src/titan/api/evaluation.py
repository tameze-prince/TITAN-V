from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.database import get_session
from titan.persistence.models import (
    EvaluationCriterionModel,
    EvaluationProfileModel,
    OperatorNotificationModel,
)
from titan.runtime.evaluator_profile_store import (
    EvaluationCriterionDefinition,
    EvaluationProfileStore,
)
from titan.runtime.operator_auth import OperatorIdentity, require_operator
from titan.runtime.resource_access import require_resource_permission


router = APIRouter(
    prefix="/api/v1/control-plane",
    tags=["evaluation"],
    dependencies=[Depends(require_operator)],
)


class EvaluationCriterionRequest(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4_000)
    kind: str = Field(default="PRESENCE", min_length=1, max_length=32)
    weight: float = Field(default=1.0, gt=0.0, le=100.0)
    required: bool = True
    position: int = Field(default=0, ge=0)


class EvaluationProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scope_type: str = Field(default="GLOBAL", pattern=r"^(GLOBAL|PROJECT)$")
    scope_id: UUID | None = None
    evaluator_kind: str = Field(default="RULE_BASED", pattern=r"^(RULE_BASED|MODEL)$")
    evaluator_model: str | None = Field(default=None, max_length=255)
    min_score: float = Field(default=1.0, ge=0.0, le=1.0)
    min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    system_prompt: str | None = Field(default=None, max_length=12_000)
    criteria: list[EvaluationCriterionRequest] = Field(min_length=1, max_length=50)
    activate: bool = True


class EvaluationCriterionResponse(BaseModel):
    id: UUID
    profile_id: UUID
    key: str
    description: str
    kind: str
    weight: float
    required: bool
    position: int
    status: str

    model_config = {"from_attributes": True}


class EvaluationProfileResponse(BaseModel):
    id: UUID
    name: str
    scope_type: str
    scope_id: UUID | None
    version: int
    status: str
    evaluator_kind: str
    evaluator_model: str | None
    min_score: float
    min_confidence: float
    created_by: str
    activated_at: datetime | None
    criteria: list[EvaluationCriterionResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class OperatorNotificationResponse(BaseModel):
    id: UUID
    project_id: UUID
    evaluation_id: UUID | None
    task_id: UUID | None
    severity: str
    notification_type: str
    title: str
    body: str
    status: str
    created_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None

    model_config = {"from_attributes": True}


@router.get(
    "/evaluator-profiles",
    response_model=list[EvaluationProfileResponse],
)
async def list_evaluator_profiles(
    name: str | None = None,
    scope_type: str | None = None,
    scope_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
    operator: OperatorIdentity = Depends(require_operator),
) -> list[EvaluationProfileResponse]:
    operator.require_permission("control_plane:read")
    store = EvaluationProfileStore()
    rows = await store.list_profiles(
        session,
        name=name,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    responses = []
    for row in rows:
        criteria = await store.criteria(session, profile_id=row.id)
        responses.append(
            EvaluationProfileResponse(
                **EvaluationProfileResponse.model_validate(row).model_dump(exclude={"criteria"}),
                criteria=[EvaluationCriterionResponse.model_validate(item) for item in criteria],
            )
        )
    return responses


@router.post(
    "/evaluator-profiles",
    response_model=EvaluationProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_evaluator_profile(
    payload: EvaluationProfileCreateRequest,
    session: AsyncSession = Depends(get_session),
    operator: OperatorIdentity = Depends(require_operator),
) -> EvaluationProfileResponse:
    operator.require_permission("policy:admin")
    if payload.scope_type == "PROJECT" and payload.scope_id is None:
        raise HTTPException(status_code=422, detail="Project profile requires scope_id")

    store = EvaluationProfileStore()
    try:
        row = await store.create(
            session,
            name=payload.name,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            evaluator_kind=payload.evaluator_kind,
            evaluator_model=payload.evaluator_model,
            min_score=payload.min_score,
            min_confidence=payload.min_confidence,
            system_prompt=payload.system_prompt,
            criteria=[
                EvaluationCriterionDefinition.model_validate(item)
                for item in payload.criteria
            ],
            created_by=operator.subject,
            activate=payload.activate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await session.commit()
    criteria = await store.criteria(session, profile_id=row.id)
    return EvaluationProfileResponse(
        **EvaluationProfileResponse.model_validate(row).model_dump(),
        criteria=[EvaluationCriterionResponse.model_validate(item) for item in criteria],
    )


@router.get(
    "/notifications",
    response_model=list[OperatorNotificationResponse],
)
async def list_operator_notifications(
    project_id: UUID | None = None,
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    operator: OperatorIdentity = Depends(require_operator),
) -> list[OperatorNotificationResponse]:
    operator.require_permission("control_plane:read")
    query = (
        select(OperatorNotificationModel)
        .order_by(OperatorNotificationModel.created_at.desc())
        .limit(limit)
    )
    if project_id is not None:
        await require_resource_permission(
            session,
            operator=operator,
            permission="control_plane:read",
            resource_type="project",
            resource_id=project_id,
        )
        query = query.where(OperatorNotificationModel.project_id == project_id)
    if unread_only:
        query = query.where(OperatorNotificationModel.status == "UNREAD")
    rows = list(await session.scalars(query))
    return [OperatorNotificationResponse.model_validate(row) for row in rows]


@router.post(
    "/notifications/{notification_id}/acknowledge",
    response_model=OperatorNotificationResponse,
)
async def acknowledge_notification(
    notification_id: UUID,
    session: AsyncSession = Depends(get_session),
    operator: OperatorIdentity = Depends(require_operator),
) -> OperatorNotificationResponse:
    operator.require_permission("control_plane:read")
    notification = await session.scalar(
        select(OperatorNotificationModel)
        .where(OperatorNotificationModel.id == notification_id)
        .with_for_update()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    await require_resource_permission(
        session,
        operator=operator,
        permission="control_plane:read",
        resource_type="project",
        resource_id=notification.project_id,
    )

    notification.status = "ACKNOWLEDGED"
    notification.acknowledged_at = datetime.now(UTC)
    notification.acknowledged_by = operator.subject
    await session.commit()
    await session.refresh(notification)
    return OperatorNotificationResponse.model_validate(notification)
