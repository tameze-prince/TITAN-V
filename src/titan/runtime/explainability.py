from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import EventModel, GovernanceDecisionModel


STAGE_BY_EVENT_PREFIX = {
    "Project": "DISCOVERY",
    "Intent": "INTENT",
    "TaskGraph": "PLANNING",
    "Workflow": "ORCHESTRATION",
    "Task": "EXECUTION",
    "Agent": "EXECUTION",
    "Model": "MODEL",
    "Artifact": "OUTPUT",
    "Recovery": "RECOVERY",
}


@dataclass(frozen=True, slots=True)
class ExplainabilityStep:
    occurred_at: datetime
    stage: str
    event_type: str
    actor_type: str
    aggregate_type: str
    aggregate_id: UUID | None
    summary: str
    details: dict


def _stage_for_event(event_type: str) -> str:
    for prefix, stage in STAGE_BY_EVENT_PREFIX.items():
        if event_type.startswith(prefix):
            return stage
    return "SYSTEM"


def _summarize_event(event: EventModel) -> str:
    payload = event.payload or {}
    for key in ("reason", "message", "error_message", "objective", "summary"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value[:500]
    return event.type.replace("_", " ")


async def build_project_explainability_trace(
    session: AsyncSession,
    *,
    project_id: UUID,
    workflow_id: UUID | None = None,
    limit: int = 500,
) -> tuple[ExplainabilityStep, ...]:
    events_statement = (
        select(EventModel)
        .where(EventModel.project_id == project_id)
        .order_by(EventModel.occurred_at.asc(), EventModel.id.asc())
        .limit(limit)
    )
    events = list(await session.scalars(events_statement))

    decisions_statement = (
        select(GovernanceDecisionModel)
        .where(GovernanceDecisionModel.project_id == project_id)
        .order_by(GovernanceDecisionModel.created_at.asc(), GovernanceDecisionModel.id.asc())
        .limit(limit)
    )
    decisions = list(await session.scalars(decisions_statement))

    steps: list[ExplainabilityStep] = []

    for event in events:
        payload = event.payload or {}
        if workflow_id is not None:
            linked_workflow = payload.get("workflow_id") or payload.get("run_id")
            if linked_workflow is not None and str(linked_workflow) != str(workflow_id):
                if event.aggregate_id != workflow_id:
                    continue

        steps.append(
            ExplainabilityStep(
                occurred_at=event.occurred_at,
                stage=_stage_for_event(event.type),
                event_type=event.type,
                actor_type=event.actor_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                summary=_summarize_event(event),
                details=payload,
            )
        )

    for decision in decisions:
        if workflow_id is not None and decision.workflow_id not in {None, workflow_id}:
            continue

        steps.append(
            ExplainabilityStep(
                occurred_at=decision.created_at,
                stage="GOVERNANCE",
                event_type=f"Governance:{decision.domain}",
                actor_type="SYSTEM",
                aggregate_type="GOVERNANCE",
                aggregate_id=decision.id,
                summary=decision.reason[:500],
                details={
                    "action": decision.action,
                    "allowed": decision.allowed,
                    "requires_human": decision.requires_human,
                    "checks": decision.checks_json,
                    "context": decision.context_json,
                    "policy_version_id": str(decision.policy_version_id)
                    if decision.policy_version_id
                    else None,
                },
            )
        )

    steps.sort(key=lambda item: (item.occurred_at, item.stage, item.event_type, str(item.aggregate_id)))
    return tuple(steps)
