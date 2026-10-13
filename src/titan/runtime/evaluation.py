from pydantic import BaseModel, Field


class EvaluationJudgeOutput(BaseModel):
    decision: str = Field(pattern=r"^(PASS|FAIL|NEEDS_REVIEW)$")
    score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    criteria: dict[str, bool] = Field(default_factory=dict)
    findings: dict[str, str] = Field(default_factory=dict)


class EvaluationReport(BaseModel):
    passed: bool
    score: float
    checks: dict[str, bool]
    message: str
    evaluator_type: str = "SYSTEM_QUALITY_GATE"
    independent: bool = True
    confidence: float = 1.0


def evaluate_execution(
    *,
    output: BaseModel,
    artifact_markdown: str,
    require_tool_execution: bool = False,
) -> EvaluationReport:
    checks = {
        "structured_output": isinstance(output, BaseModel),
        "summary_present": bool(getattr(output, "summary", "").strip()),
        "result_present": bool(getattr(output, "result", {})),
        "artifact_present": bool(artifact_markdown.strip()),
    }
    if require_tool_execution:
        result = getattr(output, "result", {})
        tool_calls = result.get("tool_calls", []) if isinstance(result, dict) else []
        tool_results = result.get("tool_results", []) if isinstance(result, dict) else []
        completed_call_ids = {
            item.get("call_id")
            for item in tool_results
            if isinstance(item, dict)
            and item.get("kind") == "tool_result"
            and item.get("status") == "COMPLETED"
            and item.get("call_id")
        }
        checks["tool_execution_present"] = any(
            isinstance(item, dict)
            and item.get("kind") == "tool_call"
            and item.get("call_id") in completed_call_ids
            for item in tool_calls
        )
    passed = all(checks.values())
    failed_count = sum(1 for value in checks.values() if not value)
    score = sum(checks.values()) / len(checks)
    confidence = max(
        0.0,
        min(1.0, 0.80 + (0.20 / len(checks)) - (0.08 * failed_count)),
    )
    return EvaluationReport(
        passed=passed,
        score=score,
        checks=checks,
        message=(
            "Independent system quality gate passed"
            if passed
            else "Independent system quality gate failed one or more checks"
        ),
        evaluator_type="SYSTEM_QUALITY_GATE",
        independent=True,
        confidence=confidence,
    )
