"""Versioned evaluator profile resolution and quality criteria."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import EvaluationCriterionModel, EvaluationProfileModel


@dataclass(frozen=True, slots=True)
class EvaluationCriterion:
    key: str
    description: str
    weight: float
    required: bool
    kind: str


@dataclass(frozen=True, slots=True)
class EvaluationProfile:
    name: str
    version: int
    evaluator_kind: str
    evaluator_model: str | None
    min_score: float
    min_confidence: float
    criteria: tuple[EvaluationCriterion, ...]


DEFAULT_PROFILE = EvaluationProfile(
    name="default-quality",
    version=1,
    evaluator_kind="RULE_BASED",
    evaluator_model=None,
    min_score=1.0,
    min_confidence=0.75,
    criteria=(
        EvaluationCriterion(
            key="structured_output",
            description="The execution output must use the declared structured contract.",
            weight=1.0,
            required=True,
            kind="STRUCTURE",
        ),
        EvaluationCriterion(
            key="summary_present",
            description="A non-empty execution summary must be present.",
            weight=1.0,
            required=True,
            kind="PRESENCE",
        ),
        EvaluationCriterion(
            key="result_present",
            description="The execution must contain non-empty structured result data.",
            weight=1.0,
            required=True,
            kind="PRESENCE",
        ),
        EvaluationCriterion(
            key="artifact_present",
            description="A non-empty artifact must be present.",
            weight=1.0,
            required=True,
            kind="PRESENCE",
        ),
    ),
)


async def resolve_active_profile(
    session: AsyncSession,
    *,
    project_id: UUID | None = None,
    name: str = "default-quality",
) -> EvaluationProfile:
    row = await session.scalar(
        select(EvaluationProfileModel)
        .where(
            EvaluationProfileModel.name == name,
            EvaluationProfileModel.status == "ACTIVE",
            (
                (EvaluationProfileModel.scope_type == "PROJECT")
                & (EvaluationProfileModel.scope_id == project_id)
            )
            | (
                (EvaluationProfileModel.scope_type == "GLOBAL")
                & (EvaluationProfileModel.scope_id.is_(None))
            ),
        )
        .order_by(
            EvaluationProfileModel.scope_type.desc(),
            EvaluationProfileModel.version.desc(),
        )
        .limit(1)
    )
    if row is None:
        return DEFAULT_PROFILE

    criteria_rows = list(
        await session.scalars(
            select(EvaluationCriterionModel)
            .where(
                EvaluationCriterionModel.profile_id == row.id,
                EvaluationCriterionModel.status == "ACTIVE",
            )
            .order_by(EvaluationCriterionModel.position.asc(), EvaluationCriterionModel.key.asc())
        )
    )
    return EvaluationProfile(
        name=row.name,
        version=row.version,
        evaluator_kind=row.evaluator_kind,
        evaluator_model=row.evaluator_model,
        min_score=row.min_score,
        min_confidence=row.min_confidence,
        criteria=tuple(
            EvaluationCriterion(
                key=item.key,
                description=item.description,
                weight=item.weight,
                required=item.required,
                kind=item.kind,
            )
            for item in criteria_rows
        ) or DEFAULT_PROFILE.criteria,
    )
