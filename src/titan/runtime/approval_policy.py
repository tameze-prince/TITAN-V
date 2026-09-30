from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import TaskModel
from titan.runtime.policy_store import PolicyDefinition, PolicyVersionStore


@dataclass(frozen=True, slots=True)
class TaskApprovalPolicy:
    quorum: int = 1
    minimum_role: str = "operator"
    escalation_role: str = "admin"
    escalation_enabled: bool = True
    escalation_after_seconds: int = 0
    delegation_allowed: bool = False
    delegation_max_ttl_seconds: int = 3_600


async def resolve_task_approval_policy(
    session: AsyncSession,
    *,
    project_id: UUID,
    task: TaskModel,
) -> TaskApprovalPolicy:
    policy = await PolicyVersionStore().resolve_effective(
        session,
        policy_name="task_approval",
        project_id=project_id,
    )
    if policy is None:
        return TaskApprovalPolicy(quorum=max(1, task.approval_quorum))

    definition = PolicyDefinition.model_validate(policy.definition_json)
    return TaskApprovalPolicy(
        quorum=max(max(1, task.approval_quorum), definition.task_approval_quorum),
        minimum_role=definition.task_approval_min_role,
        escalation_role=definition.task_approval_escalation_role,
        escalation_enabled=definition.task_approval_escalation_enabled,
        escalation_after_seconds=definition.task_approval_escalation_after_seconds,
        delegation_allowed=definition.delegation_allowed,
        delegation_max_ttl_seconds=definition.delegation_max_ttl_seconds,
    )
