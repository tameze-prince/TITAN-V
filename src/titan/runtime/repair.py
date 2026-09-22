from dataclasses import dataclass
from typing import Any

from titan.runtime.evaluation import EvaluationReport


@dataclass(frozen=True, slots=True)
class RepairPolicy:
    max_attempts: int = 2

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("Repair max_attempts must be positive")


@dataclass(frozen=True, slots=True)
class RepairPlan:
    diagnosis: str
    corrective_action: str
    failed_checks: tuple[str, ...]
    attempt: int


class AgentEvaluationFailure(RuntimeError):
    def __init__(
        self,
        *,
        evaluation: EvaluationReport,
        plan: RepairPlan,
    ) -> None:
        super().__init__(evaluation.message)
        self.evaluation = evaluation
        self.plan = plan


class RepairPlanner:
    def build(
        self,
        *,
        evaluation: EvaluationReport,
        attempt: int,
        prior_context: dict[str, Any] | None = None,
    ) -> RepairPlan:
        failed_checks = tuple(
            name for name, passed in evaluation.checks.items() if not passed
        )
        if not failed_checks:
            failed_checks = ("quality_gate",)

        diagnosis = (
            f"Evaluation score {evaluation.score:.2f}; "
            f"failed checks: {', '.join(failed_checks)}."
        )
        if prior_context and prior_context.get("repair_context"):
            diagnosis = (
                f"{diagnosis} Previous repair context: "
                f"{prior_context['repair_context']}"
            )

        corrective_action = (
            "Address every failed quality check before producing the final result. "
            "Prioritize concrete evidence and complete artifact generation."
        )

        return RepairPlan(
            diagnosis=diagnosis,
            corrective_action=corrective_action,
            failed_checks=failed_checks,
            attempt=attempt,
        )
