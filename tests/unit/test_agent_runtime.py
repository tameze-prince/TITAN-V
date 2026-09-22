import pytest

from titan.runtime.contracts import AgentTaskContext, AgentModelOutput
from titan.runtime.providers import LocalStructuredProvider, ModelRequest, ProviderRouter
from titan.runtime.service import AgentRuntime


@pytest.mark.asyncio
async def test_agent_runtime_executes_structured_local_task() -> None:
    runtime = AgentRuntime()
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
    runtime = AgentRuntime()
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

    runtime = AgentRuntime()
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
