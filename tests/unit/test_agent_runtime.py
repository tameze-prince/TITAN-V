import pytest

from titan.runtime.contracts import AgentContract, AgentTaskContext, AgentModelOutput
from titan.runtime.providers import LocalStructuredProvider, ModelRequest, ProviderRouter
from titan.runtime.service import (
    AgentContractRegistry,
    AgentRuntime,
    ENGINEERING_AGENT,
    GENERAL_AGENT,
)


def build_local_runtime() -> AgentRuntime:
    """Use deterministic providers regardless of local .env configuration."""
    contracts = AgentContractRegistry(
        (
            GENERAL_AGENT.model_copy(update={"model": "local"}),
            ENGINEERING_AGENT.model_copy(update={"model": "local"}),
        )
    )
    providers = ProviderRouter({"local": LocalStructuredProvider()})
    return AgentRuntime(contracts=contracts, providers=providers)


@pytest.mark.asyncio
async def test_agent_runtime_executes_structured_local_task() -> None:
    runtime = build_local_runtime()
    context = AgentTaskContext(
        task_id="task-1",
        run_id="run-1",
        project_id="project-1",
        title="Assess repository",
        objective="Produce a structured technical assessment",
        risk_level="R1",
    )

    result = await runtime.execute(context)

    assert result.status == "COMPLETED"
    assert result.provider == "local"
    assert isinstance(result.output, AgentModelOutput)
    assert result.output.summary
    assert result.output.artifact_markdown
    assert result.evaluation["passed"] is True


@pytest.mark.asyncio
async def test_agent_runtime_rejects_task_above_agent_risk_ceiling() -> None:
    runtime = build_local_runtime()
    context = AgentTaskContext(
        task_id="task-2",
        run_id="run-2",
        project_id="project-1",
        title="High risk task",
        objective="Attempt a high risk operation",
        risk_level="R2",
    )

    with pytest.raises(PermissionError, match="risk"):
        await runtime.execute(context)


@pytest.mark.asyncio
async def test_local_provider_returns_requested_structured_model() -> None:
    provider = LocalStructuredProvider()
    response = await provider.generate(
        ModelRequest(
            system_prompt="system",
            user_prompt="do work",
            model="local",
        ),
        AgentModelOutput,
    )

    assert response.provider == "local"
    assert isinstance(response.parsed, AgentModelOutput)


def test_provider_router_rejects_unknown_provider() -> None:
    router = ProviderRouter({"local": LocalStructuredProvider()})

    with pytest.raises(KeyError, match="not registered"):
        router.resolve("unknown:model")


@pytest.mark.asyncio
async def test_engineering_agent_uses_tool_loop_boundary() -> None:
    from uuid import uuid4

    runtime = build_local_runtime()
    context = AgentTaskContext(
        task_id=str(uuid4()),
        run_id=str(uuid4()),
        project_id=str(uuid4()),
        title="Inspect workspace",
        objective="Inspect the assigned engineering workspace and summarize the task.",
        risk_level="R1",
    )

    result = await runtime.execute(context, agent_name="engineering-executor")

    assert result.status == "COMPLETED"
    assert result.evaluation["passed"] is True
    assert "tool_calls" in result.output.result


@pytest.mark.asyncio
async def test_agent_runtime_retries_after_evaluation_failure(monkeypatch) -> None:
    from titan.runtime.evaluation import EvaluationReport
    from titan.runtime.providers import ModelResponse, ProviderRouter
    from titan.runtime.repair import RepairPolicy
    from titan.runtime.service import AgentContractRegistry

    class FakeProvider:
        name = "fake"

        async def generate(self, request, output_model):
            return ModelResponse(
                provider=self.name,
                model="fake-model",
                parsed=AgentModelOutput(
                    summary="valid summary",
                    result={"ok": True},
                    artifact_markdown="# Artifact",
                ),
            )

    checks = iter(
        [
            EvaluationReport(
                passed=False,
                score=0.5,
                checks={"artifact": False, "summary": True},
                message="Artifact is missing",
            ),
            EvaluationReport(
                passed=True,
                score=1.0,
                checks={"artifact": True, "summary": True},
                message="Passed",
            ),
        ]
    )

    def fake_evaluate_execution(
        *, output, artifact_markdown, require_tool_execution=False
    ):
        return next(checks)

    monkeypatch.setattr("titan.runtime.service.evaluate_execution", fake_evaluate_execution)

    contract = AgentContract(
        name="repair-agent",
        role="Repair",
        instructions="Repair and complete the task.",
        capabilities=(),
        model="fake:model",
        risk_ceiling="R1",
    )
    runtime = AgentRuntime(
        contracts=AgentContractRegistry((contract,)),
        providers=ProviderRouter({"fake": FakeProvider()}),
    )
    runtime.repair_policy = RepairPolicy(max_attempts=1)

    result = await runtime.execute(
        AgentTaskContext(
            task_id="task",
            run_id="run",
            project_id="project",
            title="Repair",
            objective="Produce an artifact",
            risk_level="R1",
        ),
        agent_name="repair-agent",
    )

    assert result.status == "COMPLETED"
    assert result.usage["repair_attempts_total"] == 1


@pytest.mark.asyncio
async def test_agent_runtime_raises_durable_evaluation_failure_after_repair_budget(monkeypatch) -> None:
    from titan.runtime.evaluation import EvaluationReport
    from titan.runtime.providers import ModelResponse, ProviderRouter
    from titan.runtime.repair import AgentEvaluationFailure, RepairPolicy
    from titan.runtime.service import AgentContractRegistry

    class FakeProvider:
        name = "fake"

        async def generate(self, request, output_model):
            return ModelResponse(
                provider=self.name,
                model="fake-model",
                parsed=AgentModelOutput(
                    summary="summary",
                    result={},
                    artifact_markdown="# Artifact",
                ),
            )

    failed = EvaluationReport(
        passed=False,
        score=0.33,
        checks={"artifact": False, "summary": True, "structure": False},
        message="Evaluation failed",
    )
    monkeypatch.setattr("titan.runtime.service.evaluate_execution", lambda **_: failed)

    contract = AgentContract(
        name="repair-agent",
        role="Repair",
        instructions="Repair and complete the task.",
        capabilities=(),
        model="fake:model",
        risk_ceiling="R1",
    )
    runtime = AgentRuntime(
        contracts=AgentContractRegistry((contract,)),
        providers=ProviderRouter({"fake": FakeProvider()}),
    )
    runtime.repair_policy = RepairPolicy(max_attempts=1)

    with pytest.raises(AgentEvaluationFailure) as exc_info:
        await runtime.execute(
            AgentTaskContext(
                task_id="task",
                run_id="run",
                project_id="project",
                title="Repair",
                objective="Produce an artifact",
                risk_level="R1",
            ),
            agent_name="repair-agent",
        )

    assert exc_info.value.plan.attempt == 2
    assert "artifact" in exc_info.value.plan.failed_checks
