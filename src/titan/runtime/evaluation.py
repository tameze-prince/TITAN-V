from pydantic import BaseModel


class EvaluationReport(BaseModel):
    passed: bool
    score: float
    checks: dict[str, bool]
    message: str


def evaluate_execution(
    *,
    output: BaseModel,
    artifact_markdown: str,
) -> EvaluationReport:
    checks = {
        "structured_output": isinstance(output, BaseModel),
        "summary_present": bool(getattr(output, "summary", "").strip()),
        "artifact_present": bool(artifact_markdown.strip()),
    }
    passed = all(checks.values())
    score = 1.0 if passed else sum(checks.values()) / len(checks)
    return EvaluationReport(
        passed=passed,
        score=score,
        checks=checks,
        message="Execution passed the baseline runtime quality gate"
        if passed
        else "Execution failed one or more baseline runtime quality checks",
    )
