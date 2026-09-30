from titan.persistence.models import EvaluationModel, EvidenceModel, RepairAttemptModel
from titan.runtime.contracts import AgentModelOutput
from titan.runtime.evaluation import evaluate_execution
from titan.runtime.evaluation_service import EvaluationCheck, EvaluationEngine
from titan.runtime.repair import RepairPolicy


def test_independent_quality_gate_requires_real_output_content() -> None:
    output = AgentModelOutput(
        summary="done",
        result={"answer": "ok"},
        artifact_markdown="# Result\n\nverified",
    )

    report = evaluate_execution(output=output, artifact_markdown=output.artifact_markdown)

    assert report.passed is True
    assert report.independent is True
    assert report.evaluator_type == "SYSTEM_QUALITY_GATE"


def test_quality_gate_rejects_empty_result() -> None:
    output = AgentModelOutput(
        summary="done",
        result={},
        artifact_markdown="# Result",
    )

    report = evaluate_execution(output=output, artifact_markdown=output.artifact_markdown)

    assert report.passed is False
    assert report.checks["result_present"] is False


def test_evaluation_engine_does_not_turn_failed_criteria_into_passes() -> None:
    result = EvaluationEngine().evaluate(
        checks=(
            EvaluationCheck(name="a", passed=True, evidence="ok"),
            EvaluationCheck(name="b", passed=False, evidence="missing"),
        )
    )

    assert result.passed is False
    assert result.score == 0.5
    assert result.checks[1].passed is False


def test_evaluation_models_expose_lineage_fields() -> None:
    assert hasattr(EvaluationModel, "artifact_id")
    assert hasattr(EvaluationModel, "independent")
    assert hasattr(EvidenceModel, "evaluation_id")
    assert hasattr(EvidenceModel, "artifact_id")
    assert hasattr(RepairAttemptModel, "max_attempts")


def test_repair_policy_remains_bounded() -> None:
    policy = RepairPolicy(max_attempts=2)

    assert policy.max_attempts == 2
