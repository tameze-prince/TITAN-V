from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import EventModel


@dataclass(frozen=True, slots=True)
class RecoveryMetrics:
    started: int
    resolved: int
    repeated_failures: int
    escalated: int
    failed_to_start: int
    terminal_attempts: int
    resolved_ratio: float
    latest_outcome: str | None


async def collect_recovery_metrics(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> RecoveryMetrics:
    events = list(
        await session.scalars(
            select(EventModel)
            .where(
                EventModel.project_id == project_id,
                EventModel.type.in_(
                    (
                        "RecoveryStarted",
                        "RecoveryResolved",
                        "RecoveryRepeatedFailure",
                        "RecoveryEscalated",
                        "RecoveryFailed",
                    )
                ),
            )
            .order_by(EventModel.occurred_at.desc())
        )
    )

    counts = {
        "RecoveryStarted": 0,
        "RecoveryResolved": 0,
        "RecoveryRepeatedFailure": 0,
        "RecoveryEscalated": 0,
        "RecoveryFailed": 0,
    }
    latest_outcome: str | None = None

    outcome_by_event = {
        "RecoveryResolved": "RESOLVED",
        "RecoveryRepeatedFailure": "REPEATED_FAILURE",
        "RecoveryEscalated": "ESCALATED",
        "RecoveryFailed": "FAILED_TO_START",
    }

    for event in events:
        counts[event.type] += 1
        if latest_outcome is None and event.type in outcome_by_event:
            latest_outcome = outcome_by_event[event.type]

    terminal_attempts = (
        counts["RecoveryResolved"]
        + counts["RecoveryRepeatedFailure"]
        + counts["RecoveryEscalated"]
        + counts["RecoveryFailed"]
    )
    resolved_ratio = (
        counts["RecoveryResolved"] / terminal_attempts
        if terminal_attempts
        else 0.0
    )

    return RecoveryMetrics(
        started=counts["RecoveryStarted"],
        resolved=counts["RecoveryResolved"],
        repeated_failures=counts["RecoveryRepeatedFailure"],
        escalated=counts["RecoveryEscalated"],
        failed_to_start=counts["RecoveryFailed"],
        terminal_attempts=terminal_attempts,
        resolved_ratio=round(resolved_ratio, 4),
        latest_outcome=latest_outcome,
    )
