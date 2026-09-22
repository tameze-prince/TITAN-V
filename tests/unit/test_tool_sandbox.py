from pathlib import Path

import pytest

from titan.runtime.sandbox import DockerSandbox, SandboxPolicy, SandboxRequest, SandboxResult
from titan.runtime.tools import ToolCall, ToolDefinition, ToolExecutionContext, ToolExecutor, ToolRegistry


class FakeSandbox:
    def __init__(self) -> None:
        self.requests: list[SandboxRequest] = []

    async def run(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        return SandboxResult(exit_code=0, stdout="ok", stderr="", duration_ms=4)


@pytest.mark.asyncio
async def test_tool_executor_enforces_allowlist_and_risk(tmp_path: Path) -> None:
    async def handler(context: ToolExecutionContext, arguments: dict) -> dict:
        return {"workspace": str(context.workspace), "command": arguments["command"]}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="sandbox.exec",
            description="test",
            risk_level="R2",
            handler=handler,
        )
    )
    executor = ToolExecutor(registry)

    context = ToolExecutionContext(
        task_id="task",
        run_id="run",
        project_id="project",
        task_risk="R2",
        agent_risk_ceiling="R2",
        workspace=tmp_path,
    )

    result = await executor.execute(
        ToolCall(name="sandbox.exec", arguments={"command": ["python", "-V"]}),
        context,
        allowed_tools=("sandbox.exec",),
    )

    assert result.status == "COMPLETED"
    assert result.output["command"] == ["python", "-V"]

    with pytest.raises(PermissionError, match="risk"):
        await executor.execute(
            ToolCall(name="sandbox.exec", arguments={"command": ["python", "-V"]}),
            context.__class__(
                task_id="task",
                run_id="run",
                project_id="project",
                task_risk="R1",
                agent_risk_ceiling="R1",
                workspace=tmp_path,
            ),
            allowed_tools=("sandbox.exec",),
        )


@pytest.mark.asyncio
async def test_sandbox_tool_uses_bound_workspace(tmp_path: Path) -> None:
    fake = FakeSandbox()

    async def handler(context: ToolExecutionContext, arguments: dict) -> dict:
        request = SandboxRequest(
            command=tuple(arguments["command"]),
            workspace=context.workspace,
        )
        result = await fake.run(request)
        return {"exit_code": result.exit_code}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="sandbox.exec",
            description="test",
            risk_level="R2",
            handler=handler,
        )
    )

    executor = ToolExecutor(registry)
    context = ToolExecutionContext(
        task_id="task",
        run_id="run",
        project_id="project",
        task_risk="R2",
        agent_risk_ceiling="R2",
        workspace=tmp_path,
    )
    result = await executor.execute(
        ToolCall(name="sandbox.exec", arguments={"command": ["python", "-c", "print(1)"]}),
        context,
        allowed_tools=("sandbox.exec",),
    )

    assert result.output["exit_code"] == 0
    assert fake.requests[0].workspace == tmp_path


def test_docker_sandbox_builds_hardened_command(tmp_path: Path) -> None:
    sandbox = DockerSandbox(SandboxPolicy(image="example:latest"))
    command = sandbox._build_command(
        SandboxRequest(command=("python", "-c", "print(1)"), workspace=tmp_path),
        tmp_path.resolve(),
    )

    assert "--network" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--cap-drop" in command
    assert "ALL" in command
    assert "--security-opt" in command
    assert "no-new-privileges" in command
    assert "--read-only" in command
    assert "--pids-limit" in command
    assert command[-4:] == ["example:latest", "python", "-c", "print(1)"]


def test_sandbox_rejects_missing_workspace(tmp_path: Path) -> None:
    sandbox = DockerSandbox()
    missing = tmp_path / "missing"

    async def run() -> None:
        await sandbox.run(SandboxRequest(command=("python", "-V"), workspace=missing))

    with pytest.raises(Exception, match="workspace"):
        import asyncio
        asyncio.run(run())
