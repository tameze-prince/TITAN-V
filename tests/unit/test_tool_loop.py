import pytest
from pathlib import Path

from titan.runtime.contracts import AgentContract, AgentTaskContext
from titan.runtime.context import ContextEngine
from titan.runtime.tool_loop import (
    AgentToolLoop,
    ModelToolCall,
    ModelToolTurn,
    ToolLoopPolicy,
)
from titan.runtime.tools import ToolDefinition, ToolExecutor, ToolExecutionContext, ToolRegistry


class FakeProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_tool_turn(
        self,
        *,
        system_prompt: str,
        user_prompt,
        tools,
        previous_response_id,
    ) -> ModelToolTurn:
        self.calls += 1
        if self.calls == 1:
            return ModelToolTurn(
                response_id="response-1",
                text="",
                tool_calls=(
                    ModelToolCall(
                        call_id="call-1",
                        name="workspace.read",
                        arguments={"path": "notes.txt"},
                    ),
                ),
            )
        return ModelToolTurn(
            response_id="response-2",
            text="Finished after inspecting the workspace.",
        )


@pytest.mark.asyncio
async def test_tool_loop_executes_tool_and_returns_final_answer(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("trusted-ish test fixture", encoding="utf-8")

    async def read_tool(context: ToolExecutionContext, arguments: dict) -> dict:
        return {"content": (context.workspace / arguments["path"]).read_text(encoding="utf-8")}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="workspace.read",
            description="Read one workspace file.",
            risk_level="R1",
            handler=read_tool,
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        )
    )

    contract = AgentContract(
        name="test-agent",
        role="Test",
        instructions="Inspect evidence and report.",
        capabilities=("analysis",),
        allowed_tools=("workspace.read",),
        risk_ceiling="R1",
        model="local",
    )
    task = AgentTaskContext(
        task_id="task-1",
        run_id="run-1",
        project_id="project-1",
        title="Inspect",
        objective="Read notes",
        risk_level="R1",
    )

    result = await AgentToolLoop(
        policy=ToolLoopPolicy(max_steps=1),
    ).run(
        provider=FakeProvider(),
        contract=contract,
        task=task,
        workspace=tmp_path,
        tools=(registry.resolve("workspace.read"),),
        executor=ToolExecutor(registry),
    )

    assert result.final_text == "Finished after inspecting the workspace."
    assert result.tool_calls[0]["name"] == "workspace.read"
    assert result.tool_results[0]["output"]["content"] == "trusted-ish test fixture"


def test_context_engine_marks_external_data_untrusted(tmp_path: Path) -> None:
    contract = AgentContract(
        name="test-agent",
        role="Test",
        instructions="Inspect evidence.",
        capabilities=("analysis",),
        model="local",
    )
    task = AgentTaskContext(
        task_id="task-1",
        run_id="run-1",
        project_id="project-1",
        title="Inspect",
        objective="Inspect evidence",
        risk_level="R1",
    )

    frame = ContextEngine().build(
        contract=contract,
        task=task,
        workspace=tmp_path,
        tools=(),
    )

    assert "untrusted external data" in frame.system_prompt
    assert "Available tools" in frame.user_prompt


class TextOnlyProvider:
    async def generate_tool_turn(
        self,
        *,
        system_prompt: str,
        user_prompt,
        tools,
        previous_response_id,
    ) -> ModelToolTurn:
        return ModelToolTurn(
            response_id=None,
            text='[[{"name": "workspace_list", "parameters": {"path": "."}}]]',
        )


@pytest.mark.asyncio
async def test_tool_loop_rejects_text_that_mimics_a_tool_call(tmp_path: Path) -> None:
    async def noop_tool(
        context: ToolExecutionContext, arguments: dict
    ) -> dict:
        return {"ok": True}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="workspace.list",
            description="List workspace entries.",
            risk_level="R1",
            handler=noop_tool,
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "additionalProperties": False,
            },
        )
    )
    contract = AgentContract(
        name="test-agent",
        role="Test",
        instructions="Use the provided tool.",
        capabilities=("analysis",),
        allowed_tools=("workspace.list",),
        risk_ceiling="R1",
        model="local",
    )
    task = AgentTaskContext(
        task_id="task-1",
        run_id="run-1",
        project_id="project-1",
        title="List files",
        objective="List files using the tool.",
        risk_level="R1",
    )

    with pytest.raises(RuntimeError, match="no native tool calls"):
        await AgentToolLoop().run(
            provider=TextOnlyProvider(),
            contract=contract,
            task=task,
            workspace=tmp_path,
            tools=(registry.resolve("workspace.list"),),
            executor=ToolExecutor(registry),
        )


class RepeatingToolProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_tool_turn(
        self,
        *,
        system_prompt: str,
        user_prompt,
        tools,
        previous_response_id,
    ) -> ModelToolTurn:
        self.calls += 1
        return ModelToolTurn(
            response_id=f"response-{self.calls}",
            text="",
            tool_calls=(
                ModelToolCall(
                    call_id=f"call-{self.calls}",
                    name="sandbox.exec",
                    arguments={"command": ["bash", "-lc", "echo hello"]},
                ),
            ),
        )


@pytest.mark.asyncio
async def test_tool_loop_reports_recent_results_when_model_never_finishes(
    tmp_path: Path,
) -> None:
    async def failing_tool(
        context: ToolExecutionContext, arguments: dict
    ) -> dict:
        raise RuntimeError("sandbox failed: bash executable not found")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="sandbox.exec",
            description="Execute a workspace command.",
            risk_level="R2",
            handler=failing_tool,
            input_schema={
                "type": "object",
                "properties": {
                    "command": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        )
    )
    contract = AgentContract(
        name="test-engineering-agent",
        role="Engineering",
        instructions="Run the command and report.",
        capabilities=("analysis",),
        allowed_tools=("sandbox.exec",),
        risk_ceiling="R2",
        model="local",
    )
    task = AgentTaskContext(
        task_id="task-diagnostics",
        run_id="run-diagnostics",
        project_id="project-diagnostics",
        title="Run a command",
        objective="Run a command in the workspace.",
        risk_level="R2",
    )

    with pytest.raises(RuntimeError, match="Recent tool results") as exc_info:
        await AgentToolLoop(policy=ToolLoopPolicy(max_steps=1)).run(
            provider=RepeatingToolProvider(),
            contract=contract,
            task=task,
            workspace=tmp_path,
            tools=(registry.resolve("sandbox.exec"),),
            executor=ToolExecutor(registry),
        )

    message = str(exc_info.value)
    assert "sandbox failed: bash executable not found" in message
    assert '"status": "FAILED"' in message

