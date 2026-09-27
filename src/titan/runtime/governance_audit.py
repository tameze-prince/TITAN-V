from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import GovernanceDecisionModel
from titan.runtime.governance import GovernanceDecision


async def record_governance_decision(
    session: AsyncSession,
    *,
    decision: GovernanceDecision,
    domain: str,
    project_id: UUID | None = None,
    workflow_id: UUID | None = None,
    task_id: UUID | None = None,
    policy_version_id: UUID | None = None,
    context: dict | None = None,
) -> GovernanceDecisionModel:
    row = GovernanceDecisionModel(
        project_id=project_id,
        workflow_id=workflow_id,
        task_id=task_id,
        policy_version_id=policy_version_id,
        domain=domain,
        action=decision.action.value,
        allowed=decision.allowed,
        requires_human=decision.requires_human,
        reason=decision.reason,
        checks_json=[
            {
                "policy": check.policy,
                "action": check.action.value,
                "reason": check.reason,
            }
            for check in decision.checks
        ],
        context_json=context or {},
    )
    session.add(row)
    await session.flush()
    return row
