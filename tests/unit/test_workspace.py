from pathlib import Path
from uuid import uuid4

import pytest

from titan.runtime.workspace import WorkspaceError, WorkspaceManager


def test_workspace_manager_creates_isolated_task_workspace(tmp_path: Path) -> None:
    project_id = str(uuid4())
    task_id = str(uuid4())
    manager = WorkspaceManager(tmp_path)

    workspace = manager.ensure(project_id, task_id)

    assert workspace.root.is_dir()
    assert workspace.root.parent.name == project_id
    assert workspace.root.name == task_id
    assert (workspace.root / ".titan-workspace.json").is_file()


def test_workspace_manager_rejects_path_escape(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path)
    workspace = manager.ensure(str(uuid4()), str(uuid4()))

    with pytest.raises(WorkspaceError, match="escapes"):
        manager.resolve_relative(workspace, "../../outside.txt")


def test_workspace_manager_rejects_non_uuid_identity(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path)

    with pytest.raises(WorkspaceError, match="UUID"):
        manager.ensure("project", "task")


class FakeTool:
    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description


class FakeListed:
    def __init__(self, tools):
        self.tools = tools


class FakeResult:
    structured_content = {"result": "ok"}
    is_error = False


class FakeClient:
    def __init__(self, target: str) -> None:
        self.target = target
        self.calls: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def list_tools(self):
        return FakeListed([FakeTool("lookup", "Look up a value"), FakeTool("blocked", "blocked")])

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return FakeResult()


@pytest.mark.asyncio
async def test_mcp_provider_registers_only_allowlisted_tools() -> None:
    from titan.runtime.mcp import MCPServerConfig, MCPToolProvider
    from titan.runtime.tools import ToolRegistry, ToolExecutionContext, ToolExecutor, ToolCall

    provider = MCPToolProvider(
        MCPServerConfig(
            name="demo",
            url="http://localhost:8000/mcp",
            tool_allowlist=("lookup",),
            default_risk="R2",
        ),
        client_factory=FakeClient,
    )
    registry = ToolRegistry()

    names = await provider.register_tools(registry)

    assert names == ("mcp.demo.lookup",)
    assert registry.resolve("mcp.demo.lookup").risk_level == "R2"

    executor = ToolExecutor(registry)
    result = await executor.execute(
        ToolCall(name="mcp.demo.lookup", arguments={"key": "alpha"}),
        ToolExecutionContext(
            task_id=str(uuid4()),
            run_id=str(uuid4()),
            project_id=str(uuid4()),
            task_risk="R2",
            agent_risk_ceiling="R2",
            workspace=Path(".").resolve(),
        ),
        allowed_tools=("mcp.demo.lookup",),
    )

    assert result.output["structured_content"] == {"result": "ok"}
