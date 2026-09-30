import pytest

from titan.runtime.contracts import AgentModelOutput
from titan.runtime.evaluation import EvaluationJudgeOutput
from titan.runtime.evaluation_service import EvaluationEngine
from titan.runtime.evaluator_profiles import (
    EvaluationCriterion,
    EvaluationProfile,
)


class FakeProvider:
    name = "fake"

    def __init__(self, result: EvaluationJudgeOutput) -> None:
        self.result = result

    async def generate(self, request, output_model):
        from titan.runtime.providers import ModelResponse

        assert output_model is EvaluationJudgeOutput
        return ModelResponse(
            provider=self.name,
            model=request.model,
            parsed=self.result,
            usage={"mode": "test"},
        )


def model_profile() -> EvaluationProfile:
    return EvaluationProfile(
        id=None,
        name="strict-model",
        version=3,
        evaluator_kind="MODEL",
        evaluator_model="fake:judge-v3",
        min_score=0.75,
        min_confidence=0.80,
        criteria=(
            EvaluationCriterion(
                key="correctness",
                description="The result addresses the objective.",
                weight=2.0,
                required=True,
                kind="MODEL",
            ),
            EvaluationCriterion(
                key="evidence",
                description="The artifact contains useful evidence.",
                weight=1.0,
                required=True,
                kind="MODEL",
            ),
        ),
    )


@pytest.mark.asyncio
async def test_model_evaluator_uses_versioned_profile_and_passes() -> None:
    provider = FakeProvider(
        EvaluationJudgeOutput(
            decision="PASS",
            score=1.0,
            confidence=0.95,
            criteria={"correctness": True, "evidence": True},
            findings={"correctness": "matches", "evidence": "present"},
        )
    )

    result = await EvaluationEngine().evaluate_with_profile(
        profile=model_profile(),
        output=AgentModelOutput(
            summary="done",
            result={"answer": "ok"},
            artifact_markdown="# Evidence",
        ),
        task_objective="Ship a verified result",
        producer_agent="producer",
        producer_model="fake:producer-v1",
        provider=provider,
        evaluator_model="fake:judge-v3",
    )

    assert result.passed is True
    assert result.independent is True
    assert result.profile_version == 3
    assert result.evaluator_type == "MODEL_INDEPENDENT"


@pytest.mark.asyncio
async def test_model_evaluator_fails_closed_when_same_model_is_used() -> None:
    provider = FakeProvider(
        EvaluationJudgeOutput(
            decision="PASS",
            score=1.0,
            confidence=1.0,
            criteria={"correctness": True, "evidence": True},
        )
    )

    result = await EvaluationEngine().evaluate_with_profile(
        profile=model_profile(),
        output=AgentModelOutput(
            summary="done",
            result={"answer": "ok"},
            artifact_markdown="# Evidence",
        ),
        task_objective="Ship a verified result",
        producer_agent="producer",
        producer_model="fake:judge-v3",
        provider=provider,
        evaluator_model="fake:judge-v3",
    )

    assert result.passed is False
    assert result.decision == "NEEDS_REVIEW"
    assert result.independent is False
    assert result.evaluator_type == "MODEL_EVALUATOR_NOT_INDEPENDENT"


@pytest.mark.asyncio
async def test_model_evaluator_fails_closed_when_provider_is_unavailable() -> None:
    result = await EvaluationEngine().evaluate_with_profile(
        profile=model_profile(),
        output=AgentModelOutput(
            summary="done",
            result={"answer": "ok"},
            artifact_markdown="# Evidence",
        ),
        task_objective="Ship a verified result",
        producer_agent="producer",
        producer_model="fake:producer-v1",
        provider=None,
    )

    assert result.passed is False
    assert result.decision == "NEEDS_REVIEW"
    assert result.independent is False


def test_profile_weights_are_preserved_in_evaluation_checks() -> None:
    engine = EvaluationEngine()
    profile = model_profile()
    result = engine.evaluate(
        profile=profile,
        checks=(
            engine_check("correctness", True, 2.0),
            engine_check("evidence", False, 1.0),
        ),
        evaluator_type="RULE_BASED_INDEPENDENT",
    )

    assert result.score == pytest.approx(2 / 3)
    assert result.passed is False


def engine_check(name: str, passed: bool, weight: float):
    from titan.runtime.evaluation_service import EvaluationCheck

    return EvaluationCheck(
        name=name,
        passed=passed,
        evidence="test",
        weight=weight,
        required=True,
    )


def test_explicit_model_fail_cannot_be_promoted_to_pass() -> None:
    engine = EvaluationEngine()
    profile = model_profile()
    result = engine.evaluate(
        profile=profile,
        checks=(
            engine_check("correctness", True, 2.0),
            engine_check("evidence", True, 1.0),
        ),
        evaluator_type="MODEL_INDEPENDENT",
        independent=True,
        confidence=0.99,
        decision="FAIL",
    )

    assert result.passed is False
    assert result.decision == "FAIL"
