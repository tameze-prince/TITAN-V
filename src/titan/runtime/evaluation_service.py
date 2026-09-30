"""Independent evaluation, evidence provenance and bounded repair persistence."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import EvidenceModel, EvaluationModel, RepairAttemptModel
from titan.runtime.contracts import AgentModelOutput
from titan.runtime.evaluation import EvaluationReport, evaluate_execution


@dataclass(frozen=True, slots=True)
class EvaluationCheck:
    name: str
    passed: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    passed: bool
    score: float
    confidence: float
    checks: tuple[EvaluationCheck, ...]
    evaluator_type: str = "SYSTEM_QUALITY_GATE"
    independent: bool = True
    evaluator_version: str = "1.0"

    def to_report(self) -> EvaluationReport:
        return EvaluationReport(
            passed=self.passed,
            score=self.score,
            checks={check.name: check.passed for check in self.checks},
            message=(
                "Independent quality gate passed"
                if self.passed
                else "Independent quality gate failed one or more criteria"
            ),
            evaluator_type=self.evaluator_type,
            independent=self.independent,
            confidence=self.confidence,
        )


class EvaluationEngine:
    EVALUATOR_TYPE = "SYSTEM_QUALITY_GATE"
    EVALUATOR_VERSION = "1.0"

    def evaluate(
        self,
        *,
        checks: tuple[EvaluationCheck, ...],
        evaluator_type: str = "RULE_BASED",
        independent: bool = True,
        evaluator_version: str = "1.0",
    ) -> EvaluationResult:
        if not checks:
            raise ValueError("Evaluation requires at least one check")

        passed_count = sum(1 for check in checks if check.passed)
        score = passed_count / len(checks)
        failed_count = len(checks) - passed_count
        confidence = max(
            0.0,
            min(1.0, 0.75 + (0.25 / len(checks)) - (0.1 * failed_count)),
        )
        return EvaluationResult(
            passed=passed_count == len(checks),
            score=score,
            confidence=confidence,
            checks=checks,
            evaluator_type=evaluator_type,
            independent=independent,
            evaluator_version=evaluator_version,
        )

    def evaluate_execution(
        self,
        *,
        output: AgentModelOutput,
        task_objective: str,
        producer_agent: str,
    ) -> EvaluationResult:
        report = evaluate_execution(
            output=output,
            artifact_markdown=output.artifact_markdown,
        )
        checks = tuple(
            EvaluationCheck(
                name=name,
                passed=passed,
                evidence=(
                    "Independent system quality-gate check; "
                    f"objective={task_objective[:180]!r}; producer={producer_agent!r}; "
                    f"result={'PASS' if passed else 'FAIL'}."
                ),
            )
            for name, passed in report.checks.items()
        )
        return self.evaluate(
            checks=checks,
            evaluator_type=self.EVALUATOR_TYPE,
            independent=True,
            evaluator_version=self.EVALUATOR_VERSION,
        )

    async def persist(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID | None,
        run_id: UUID | None,
        result: EvaluationResult,
        artifact_id: UUID | None = None,
        producer_agent: str | None = None,
        repair_attempt: int = 0,
    ) -> EvaluationModel:
        if repair_attempt < 0:
            raise ValueError("Repair attempt cannot be negative")

        evaluation = EvaluationModel(
            id=uuid4(),
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            artifact_id=artifact_id,
            evaluator_type=result.evaluator_type,
            evaluator_version=result.evaluator_version,
            producer_agent=producer_agent,
            independent=result.independent,
            decision="PASS" if result.passed else "FAIL",
            status="PASSED" if result.passed else "FAILED",
            score=result.score,
            confidence=result.confidence,
            repair_attempt=repair_attempt,
            criteria={check.name: check.passed for check in result.checks},
            findings={
                "evaluator": result.evaluator_type,
                "evaluator_version": result.evaluator_version,
                "independent": result.independent,
                "checks": [
                    {
                        "name": check.name,
                        "passed": check.passed,
                        "evidence": check.evidence,
                    }
                    for check in result.checks
                ],
            },
            completed_at=datetime.now(UTC),
        )
        session.add(evaluation)
        await session.flush()
        return evaluation

    async def persist_evidence(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID | None,
        evaluation_id: UUID,
        artifact_id: UUID | None,
        result: EvaluationResult,
    ) -> tuple[EvidenceModel, ...]:
        rows: list[EvidenceModel] = []
        for check in result.checks:
            row = EvidenceModel(
                id=uuid4(),
                project_id=project_id,
                task_id=task_id,
                evaluation_id=evaluation_id,
                artifact_id=artifact_id,
                evidence_type="EVALUATION_CRITERION",
                title=check.name,
                content=check.evidence,
                source_ref=str(evaluation_id),
                confidence=1.0 if check.passed else 0.95,
                metadata_json={
                    "criterion": check.name,
                    "passed": check.passed,
                    "evaluator_type": result.evaluator_type,
                    "evaluator_version": result.evaluator_version,
                    "independent": result.independent,
                },
            )
            session.add(row)
            rows.append(row)
        await session.flush()
        return tuple(rows)

    async def plan_repair(
        self,
        session: AsyncSession,
        *,
        evaluation_id: UUID,
        task_id: UUID | None,
        attempt: int,
        diagnosis: str,
        corrective_action: str,
        max_attempts: int,
    ) -> RepairAttemptModel:
        if attempt < 1:
            raise ValueError("Repair attempt must be positive")
        if max_attempts < 1:
            raise ValueError("Repair max_attempts must be positive")
        if attempt > max_attempts:
            raise ValueError("Repair attempt exceeds the configured maximum")

        repair = RepairAttemptModel(
            id=uuid4(),
            evaluation_id=evaluation_id,
            task_id=task_id,
            attempt=attempt,
            max_attempts=max_attempts,
            diagnosis=diagnosis,
            corrective_action=corrective_action,
            status="PLANNED",
        )
        session.add(repair)
        await session.flush()
        return repair
