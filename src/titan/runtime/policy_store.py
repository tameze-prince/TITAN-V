from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import PolicyVersionModel


class PolicyDefinition(BaseModel):
    max_task_risk: str = Field(default="R1", pattern=r"^R[0-4]$")
    minimum_quality_tier: int = Field(default=1, ge=0, le=100)
    max_model_cost: float = Field(default=0.0, ge=0.0)
    recovery_enabled: bool = False
    recovery_max_attempts: int = Field(default=2, ge=1, le=20)
    recovery_min_autonomy_level: int = Field(default=3, ge=0, le=5)
    recovery_max_auto_risk_level: str = Field(default="R1", pattern=r"^R[0-4]$")
    require_human_approval_for_recovery: bool = False
    task_approval_quorum: int = Field(default=1, ge=1, le=10)
    task_approval_min_role: str = Field(default="operator", pattern=r"^(viewer|operator|admin)$")
    task_approval_escalation_role: str = Field(default="admin", pattern=r"^(viewer|operator|admin)$")
    task_approval_escalation_enabled: bool = True
    task_approval_escalation_after_seconds: int = Field(default=0, ge=0, le=86_400)
    delegation_allowed: bool = False
    delegation_max_ttl_seconds: int = Field(default=3_600, ge=60, le=86_400)


class PolicyVersionStore:
    """Durable policy lifecycle with deterministic versioning and activation."""

    async def create(
        self,
        session: AsyncSession,
        *,
        policy_name: str,
        scope_type: str = "GLOBAL",
        scope_id: UUID | None = None,
        definition: PolicyDefinition | dict | None = None,
        created_by: str = "SYSTEM",
        activate: bool = True,
    ) -> PolicyVersionModel:
        if not policy_name.strip():
            raise ValueError("Policy name cannot be empty")

        normalized_scope = scope_type.strip().upper()
        if normalized_scope not in {"GLOBAL", "PROJECT", "AGENT"}:
            raise ValueError("Unsupported policy scope type")
        if normalized_scope == "GLOBAL" and scope_id is not None:
            raise ValueError("Global policies cannot have a scope id")
        if normalized_scope != "GLOBAL" and scope_id is None:
            raise ValueError(f"{normalized_scope} policies require a scope id")

        model = (
            definition
            if isinstance(definition, PolicyDefinition)
            else PolicyDefinition.model_validate(definition or {})
        )

        latest = await session.scalar(
            select(func.max(PolicyVersionModel.version)).where(
                PolicyVersionModel.scope_type == normalized_scope,
                PolicyVersionModel.scope_id == scope_id,
                PolicyVersionModel.policy_name == policy_name.strip(),
            )
        )
        version = int(latest or 0) + 1

        if activate:
            await session.execute(
                update(PolicyVersionModel)
                .where(
                    PolicyVersionModel.scope_type == normalized_scope,
                    PolicyVersionModel.scope_id == scope_id,
                    PolicyVersionModel.policy_name == policy_name.strip(),
                    PolicyVersionModel.status == "ACTIVE",
                )
                .values(status="SUPERSEDED")
            )

        row = PolicyVersionModel(
            scope_type=normalized_scope,
            scope_id=scope_id,
            policy_name=policy_name.strip(),
            version=version,
            status="ACTIVE" if activate else "DRAFT",
            definition_json=model.model_dump(mode="json"),
            created_by=created_by,
            activated_at=datetime.now(UTC) if activate else None,
        )
        session.add(row)
        await session.flush()
        return row

    async def get_active(
        self,
        session: AsyncSession,
        *,
        policy_name: str,
        scope_type: str = "GLOBAL",
        scope_id: UUID | None = None,
    ) -> PolicyVersionModel | None:
        return await session.scalar(
            select(PolicyVersionModel)
            .where(
                PolicyVersionModel.policy_name == policy_name,
                PolicyVersionModel.scope_type == scope_type.upper(),
                PolicyVersionModel.scope_id == scope_id,
                PolicyVersionModel.status == "ACTIVE",
            )
            .order_by(PolicyVersionModel.version.desc())
            .limit(1)
        )

    async def list_versions(
        self,
        session: AsyncSession,
        *,
        policy_name: str | None = None,
        scope_type: str | None = None,
        scope_id: UUID | None = None,
    ) -> list[PolicyVersionModel]:
        statement = select(PolicyVersionModel).order_by(
            PolicyVersionModel.policy_name.asc(),
            PolicyVersionModel.version.desc(),
        )
        if policy_name is not None:
            statement = statement.where(
                PolicyVersionModel.policy_name == policy_name,
            )
        if scope_type is not None:
            statement = statement.where(
                PolicyVersionModel.scope_type == scope_type.upper(),
            )
        if scope_id is not None:
            statement = statement.where(
                PolicyVersionModel.scope_id == scope_id,
            )
        return list(await session.scalars(statement))


    async def resolve_effective(
        self,
        session: AsyncSession,
        *,
        policy_name: str,
        project_id: UUID | None = None,
        agent_id: UUID | None = None,
    ) -> PolicyVersionModel | None:
        scopes: list[tuple[str, UUID | None]] = []
        if agent_id is not None:
            scopes.append(("AGENT", agent_id))
        if project_id is not None:
            scopes.append(("PROJECT", project_id))
        scopes.append(("GLOBAL", None))

        for scope_type, scope_id in scopes:
            policy = await self.get_active(
                session,
                policy_name=policy_name,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            if policy is not None:
                return policy

        return None
