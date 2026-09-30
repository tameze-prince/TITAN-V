from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import EvaluationCriterionModel, EvaluationProfileModel


class EvaluationCriterionDefinition(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4_000)
    kind: str = Field(default="PRESENCE", min_length=1, max_length=32)
    weight: float = Field(default=1.0, gt=0.0, le=100.0)
    required: bool = True
    position: int = Field(default=0, ge=0)


class EvaluationProfileStore:
    async def create(
        self,
        session: AsyncSession,
        *,
        name: str,
        scope_type: str = "GLOBAL",
        scope_id: UUID | None = None,
        evaluator_kind: str = "RULE_BASED",
        evaluator_model: str | None = None,
        min_score: float = 1.0,
        min_confidence: float = 0.75,
        system_prompt: str | None = None,
        criteria: list[EvaluationCriterionDefinition],
        created_by: str = "SYSTEM",
        activate: bool = True,
    ) -> EvaluationProfileModel:
        normalized_scope = scope_type.strip().upper()
        normalized_kind = evaluator_kind.strip().upper()

        if normalized_scope not in {"GLOBAL", "PROJECT"}:
            raise ValueError("Evaluator profiles support GLOBAL or PROJECT scope")
        if normalized_scope == "GLOBAL" and scope_id is not None:
            raise ValueError("Global evaluator profiles cannot have a scope id")
        if normalized_scope == "PROJECT" and scope_id is None:
            raise ValueError("Project evaluator profiles require a scope id")
        if normalized_kind not in {"RULE_BASED", "MODEL"}:
            raise ValueError("Unsupported evaluator kind")
        if not criteria:
            raise ValueError("Evaluator profile requires at least one criterion")
        keys = [item.key.strip() for item in criteria]
        if len(keys) != len(set(keys)):
            raise ValueError("Evaluator criterion keys must be unique")
        if normalized_kind == "MODEL" and not (evaluator_model or "").strip():
            raise ValueError("Model evaluator profiles require evaluator_model")

        latest = await session.scalar(
            select(func.max(EvaluationProfileModel.version)).where(
                EvaluationProfileModel.name == name.strip(),
                EvaluationProfileModel.scope_type == normalized_scope,
                EvaluationProfileModel.scope_id == scope_id,
            )
        )
        version = int(latest or 0) + 1

        if activate:
            await session.execute(
                update(EvaluationProfileModel)
                .where(
                    EvaluationProfileModel.name == name.strip(),
                    EvaluationProfileModel.scope_type == normalized_scope,
                    EvaluationProfileModel.scope_id == scope_id,
                    EvaluationProfileModel.status == "ACTIVE",
                )
                .values(status="SUPERSEDED")
            )

        now = datetime.now(UTC)
        row = EvaluationProfileModel(
            name=name.strip(),
            scope_type=normalized_scope,
            scope_id=scope_id,
            version=version,
            status="ACTIVE" if activate else "DRAFT",
            evaluator_kind=normalized_kind,
            evaluator_model=evaluator_model.strip() if evaluator_model else None,
            min_score=min_score,
            min_confidence=min_confidence,
            system_prompt=system_prompt,
            created_by=created_by,
            activated_at=now if activate else None,
        )
        session.add(row)
        await session.flush()

        for item in criteria:
            session.add(
                EvaluationCriterionModel(
                    profile_id=row.id,
                    key=item.key.strip(),
                    description=item.description.strip(),
                    kind=item.kind.strip().upper(),
                    weight=item.weight,
                    required=item.required,
                    position=item.position,
                    status="ACTIVE",
                )
            )
        await session.flush()
        return row

    async def activate(
        self,
        session: AsyncSession,
        *,
        profile_id: UUID,
    ) -> EvaluationProfileModel:
        row = await session.scalar(
            select(EvaluationProfileModel)
            .where(EvaluationProfileModel.id == profile_id)
        )
        if row is None:
            raise ValueError("Evaluator profile not found")

        await session.execute(
            update(EvaluationProfileModel)
            .where(
                EvaluationProfileModel.name == row.name,
                EvaluationProfileModel.scope_type == row.scope_type,
                EvaluationProfileModel.scope_id == row.scope_id,
                EvaluationProfileModel.status == "ACTIVE",
                EvaluationProfileModel.id != row.id,
            )
            .values(status="SUPERSEDED")
        )
        row.status = "ACTIVE"
        row.activated_at = datetime.now(UTC)
        await session.flush()
        return row

    async def list_profiles(
        self,
        session: AsyncSession,
        *,
        name: str | None = None,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
    ) -> list[EvaluationProfileModel]:
        query = select(EvaluationProfileModel).order_by(
            EvaluationProfileModel.name.asc(),
            EvaluationProfileModel.version.desc(),
        )
        if name:
            query = query.where(EvaluationProfileModel.name == name)
        if scope_type:
            query = query.where(EvaluationProfileModel.scope_type == scope_type.upper())
        if scope_id:
            query = query.where(EvaluationProfileModel.scope_id == scope_id)
        return list(await session.scalars(query))

    async def criteria(
        self,
        session: AsyncSession,
        *,
        profile_id: UUID,
    ) -> list[EvaluationCriterionModel]:
        return list(
            await session.scalars(
                select(EvaluationCriterionModel)
                .where(EvaluationCriterionModel.profile_id == profile_id)
                .order_by(EvaluationCriterionModel.position.asc(), EvaluationCriterionModel.key.asc())
            )
        )
