from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import EvaluationModel, RepairAttemptModel


@dataclass(frozen=True, slots=True)
class EvaluationCheck:
    name: str
    passed: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    passed: bool
    score: float
    checks: tuple[EvaluationCheck, ...]
    evaluator_type: str = "RULE_BASED"


class EvaluationEngine:
    def evaluate(
        self,
        *,
        checks: tuple[EvaluationCheck, ...],
        evaluator_type: str = "RULE_BASED",
    ) -> EvaluationResult:
        if not checks:
            raise ValueError("Evaluation requires at least one check")

        passed_count = sum(1 for check in checks if check.passed)
        score = passed_count / len(checks)

        return EvaluationResult(
            passed=passed_count == len(checks),
            score=score,
            checks=checks,
            evaluator_type=evaluator_type,
        )

    async def persist(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID | None,
        run_id: UUID | None,
        result: EvaluationResult,
    ) -> EvaluationModel:
        now = datetime.now(UTC)
        evaluation = EvaluationModel(
            id=uuid4(),
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            evaluator_type=result.evaluator_type,
            status="PASSED" if result.passed else "FAILED",
            score=result.score,
            criteria={check.name: True for check in result.checks},
            findings={
                "checks": [
                    {
                        "name": check.name,
                        "passed": check.passed,
                        "evidence": check.evidence,
                    }
                    for check in result.checks
                ]
            },
            completed_at=now,
        )
        session.add(evaluation)
        await session.flush()
        return evaluation

    async def plan_repair(
        self,
        session: AsyncSession,
        *,
        evaluation_id: UUID,
        task_id: UUID | None,
        attempt: int,
        diagnosis: str,
        corrective_action: str,
    ) -> RepairAttemptModel:
        if attempt < 1:
            raise ValueError("Repair attempt must be positive")

        repair = RepairAttemptModel(
            id=uuid4(),
            evaluation_id=evaluation_id,
            task_id=task_id,
            attempt=attempt,
            diagnosis=diagnosis,
            corrective_action=corrective_action,
            status="PLANNED",
        )
        session.add(repair)
        await session.flush()
        return repair
