import pytest
from pathlib import Path

from titan.runtime.contracts import AgentContract, AgentTaskContext
from titan.runtime.context import ContextEngine
from titan.runtime.tool_loop import AgentToolLoop, ModelToolCall, ModelToolTurn
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

    result = await AgentToolLoop().run(
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
