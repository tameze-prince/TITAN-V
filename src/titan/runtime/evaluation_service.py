"""Independent evaluation, versioned profiles, evidence provenance and bounded repair."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import EvidenceModel, EvaluationModel, RepairAttemptModel
from titan.runtime.contracts import AgentModelOutput
from titan.runtime.evaluation import EvaluationJudgeOutput, EvaluationReport
from titan.runtime.evaluator_profiles import EvaluationProfile


@dataclass(frozen=True, slots=True)
class EvaluationCheck:
    name: str
    passed: bool
    evidence: str
    weight: float = 1.0
    required: bool = True


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    passed: bool
    score: float
    confidence: float
    checks: tuple[EvaluationCheck, ...]
    evaluator_type: str = "SYSTEM_QUALITY_GATE"
    independent: bool = True
    evaluator_version: str = "1.0"
    profile_id: UUID | None = None
    profile_name: str = "default-quality"
    profile_version: int = 1
    decision: str = "PASS"

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

    def _score(self, checks: tuple[EvaluationCheck, ...]) -> float:
        total_weight = sum(max(0.0, check.weight) for check in checks) or 1.0
        passed_weight = sum(
            max(0.0, check.weight) for check in checks if check.passed
        )
        return passed_weight / total_weight

    def evaluate(
        self,
        *,
        checks: tuple[EvaluationCheck, ...],
        evaluator_type: str = EVALUATOR_TYPE,
        independent: bool = True,
        evaluator_version: str = EVALUATOR_VERSION,
        profile: EvaluationProfile | None = None,
        confidence: float | None = None,
        decision: str | None = None,
    ) -> EvaluationResult:
        if not checks:
            raise ValueError("Evaluation requires at least one check")

        score = self._score(checks)
        failed_required = any(
            check.required and not check.passed for check in checks
        )
        inferred_confidence = (
            confidence
            if confidence is not None
            else max(
                0.0,
                min(
                    1.0,
                    0.80
                    + (0.20 / len(checks))
                    - (0.08 * sum(1 for check in checks if not check.passed)),
                ),
            )
        )
        min_score = profile.min_score if profile else 1.0
        min_confidence = profile.min_confidence if profile else 0.75
        passed = (
            not failed_required
            and score >= min_score
            and inferred_confidence >= min_confidence
        )
        return EvaluationResult(
            passed=passed,
            score=score,
            confidence=max(0.0, min(1.0, inferred_confidence)),
            checks=checks,
            evaluator_type=evaluator_type,
            independent=independent,
            evaluator_version=evaluator_version,
            profile_id=profile.id if profile else None,
            profile_name=profile.name if profile else "default-quality",
            profile_version=profile.version if profile else 1,
            decision=decision or ("PASS" if passed else "FAIL"),
        )

    async def evaluate_with_profile(
        self,
        *,
        profile: EvaluationProfile,
        output: AgentModelOutput,
        task_objective: str,
        producer_agent: str,
        provider=None,
        evaluator_model: str | None = None,
        producer_model: str | None = None,
    ) -> EvaluationResult:
        if profile.evaluator_kind.upper() == "MODEL":
            resolved_evaluator_model = evaluator_model or profile.evaluator_model
            if (
                resolved_evaluator_model
                and producer_model
                and resolved_evaluator_model == producer_model
            ):
                return self.evaluate(
                    profile=profile,
                    checks=(
                        EvaluationCheck(
                            name="evaluator_independence",
                            passed=False,
                            evidence=(
                                "The configured evaluator model is identical to the "
                                "producer model; evaluation is not considered independent."
                            ),
                            required=True,
                        ),
                    ),
                    evaluator_type="MODEL_EVALUATOR_NOT_INDEPENDENT",
                    independent=False,
                    evaluator_version=str(profile.version),
                    confidence=0.0,
                    decision="NEEDS_REVIEW",
                )
            if provider is None:
                return self.evaluate(
                    profile=profile,
                    checks=(
                        EvaluationCheck(
                            name="evaluator_available",
                            passed=False,
                            evidence="Independent model evaluator is unavailable.",
                            required=True,
                        ),
                    ),
                    evaluator_type="MODEL_EVALUATOR_UNAVAILABLE",
                    independent=False,
                    evaluator_version=str(profile.version),
                    confidence=0.0,
                    decision="NEEDS_REVIEW",
                )

            criteria_text = "\n".join(
                f"- {item.key}: {item.description} (required={item.required}, weight={item.weight})"
                for item in profile.criteria
            )
            judge_system = profile.system_prompt or (
                "You are TITAN V's independent evaluator. "
                "You did not produce the artifact. Evaluate only the supplied task output "
                "against the versioned criteria. Never infer missing evidence. "
                "Return a strict structured judgment."
            )
            judge_prompt = (
                f"Task objective:\n{task_objective[:12000]}\n\n"
                f"Producer agent:\n{producer_agent}\n\n"
                f"Criteria:\n{criteria_text}\n\n"
                "Output summary:\n"
                f"{output.summary[:12000]}\n\n"
                "Structured result:\n"
                f"{str(output.result)[:16000]}\n\n"
                "Artifact:\n"
                f"{output.artifact_markdown[:16000]}"
            )
            from titan.runtime.providers import ModelRequest

            try:
                response = await provider.generate(
                    ModelRequest(
                        system_prompt=judge_system,
                        user_prompt=judge_prompt,
                        model=resolved_evaluator_model or "local",
                        metadata={
                            "objective": task_objective,
                            "producer_agent": producer_agent,
                            "evaluator_profile": profile.name,
                            "evaluator_profile_version": profile.version,
                        },
                    ),
                    EvaluationJudgeOutput,
                )
            except Exception as exc:
                return self.evaluate(
                    profile=profile,
                    checks=(
                        EvaluationCheck(
                            name="evaluator_available",
                            passed=False,
                            evidence=f"Independent model evaluator failed: {type(exc).__name__}.",
                            required=True,
                        ),
                    ),
                    evaluator_type="MODEL_EVALUATOR_UNAVAILABLE",
                    independent=False,
                    evaluator_version=str(profile.version),
                    confidence=0.0,
                    decision="NEEDS_REVIEW",
                )

            judge = response.parsed
            checks = tuple(
                EvaluationCheck(
                    name=item.key,
                    passed=bool(judge.criteria.get(item.key, False)),
                    evidence=str(judge.findings.get(item.key, "")),
                    weight=item.weight,
                    required=item.required,
                )
                for item in profile.criteria
            )
            return self.evaluate(
                profile=profile,
                checks=checks,
                evaluator_type="MODEL_INDEPENDENT",
                independent=True,
                evaluator_version=str(profile.version),
                confidence=judge.confidence,
                decision=judge.decision,
            )

        checks = []
        for item in profile.criteria:
            if item.kind == "STRUCTURE":
                passed = isinstance(output, AgentModelOutput)
            elif item.kind == "PRESENCE":
                target = output.summary if item.key == "summary_present" else (
                    output.artifact_markdown if item.key == "artifact_present" else output.result
                )
                passed = bool(target)
            else:
                passed = False
            checks.append(
                EvaluationCheck(
                    name=item.key,
                    passed=passed,
                    evidence=(
                        f"Rule-based evaluator checked criterion '{item.key}' "
                        f"using kind '{item.kind}'."
                    ),
                    weight=item.weight,
                    required=item.required,
                )
            )

        return self.evaluate(
            profile=profile,
            checks=tuple(checks),
            evaluator_type="RULE_BASED_INDEPENDENT",
            independent=True,
            evaluator_version=str(profile.version),
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
            profile_id=result.profile_id,
            profile_version=result.profile_version,
            evaluator_type=result.evaluator_type,
            evaluator_version=result.evaluator_version,
            producer_agent=producer_agent,
            independent=result.independent,
            decision=result.decision,
            status="PASSED" if result.passed else ("NEEDS_REVIEW" if result.decision == "NEEDS_REVIEW" else "FAILED"),
            score=result.score,
            confidence=result.confidence,
            repair_attempt=repair_attempt,
            criteria={check.name: check.passed for check in result.checks},
            findings={
                "evaluator": result.evaluator_type,
                "evaluator_version": result.evaluator_version,
                "profile_name": result.profile_name,
                "profile_version": result.profile_version,
                "independent": result.independent,
                "checks": [
                    {
                        "name": check.name,
                        "passed": check.passed,
                        "evidence": check.evidence,
                        "weight": check.weight,
                        "required": check.required,
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
                    "weight": check.weight,
                    "required": check.required,
                    "evaluator_type": result.evaluator_type,
                    "evaluator_version": result.evaluator_version,
                    "profile_id": str(result.profile_id) if result.profile_id else None,
                    "profile_name": result.profile_name,
                    "profile_version": result.profile_version,
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
