from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from titan.runtime.policies import RISK_ORDER, RuntimePolicy
from titan.runtime.sandbox import DockerSandbox, SandboxRequest


ToolHandler = Callable[["ToolExecutionContext", dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    task_id: str
    run_id: str
    project_id: str
    task_risk: str
    agent_risk_ceiling: str
    workspace: Path


class ToolCall(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolExecutionResult(BaseModel):
    tool_name: str
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    risk_level: str = "R1"
    handler: ToolHandler | None = None
    input_schema: dict[str, Any] | None = None
    strict: bool = True


class ToolRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._items:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        if tool.risk_level not in RISK_ORDER:
            raise ValueError(f"Unsupported tool risk level: {tool.risk_level}")
        self._items[tool.name] = tool

    def resolve(self, name: str) -> ToolDefinition:
        try:
            return self._items[name]
        except KeyError as exc:
            raise KeyError(f"Tool '{name}' is not registered") from exc

    def resolve_many(self, names: tuple[str, ...]) -> tuple[ToolDefinition, ...]:
        return tuple(self.resolve(name) for name in names)


class ToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        policy: RuntimePolicy | None = None,
    ) -> None:
        self.registry = registry
        self.policy = policy or RuntimePolicy()

    async def execute(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        *,
        allowed_tools: tuple[str, ...],
    ) -> ToolExecutionResult:
        definition = self.registry.resolve(call.name)

        decision = self.policy.check_tool(
            task_risk=context.task_risk,
            agent_risk_ceiling=context.agent_risk_ceiling,
            tool_risk=definition.risk_level,
            tool_name=definition.name,
            allowed_tools=allowed_tools,
        )
        if not decision.allowed:
            raise PermissionError(decision.reason)

        if definition.handler is None:
            raise RuntimeError(f"Tool '{definition.name}' has no execution handler")

        output = await definition.handler(context, call.arguments)
        return ToolExecutionResult(
            tool_name=definition.name,
            status="COMPLETED",
            output=output,
        )


def build_default_tool_registry(
    *,
    sandbox: DockerSandbox | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    configured_sandbox = sandbox or DockerSandbox()

    async def sandbox_exec(
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        raw_command = arguments.get("command")
        if not isinstance(raw_command, list) or not raw_command or not all(
            isinstance(item, str) and item for item in raw_command
        ):
            raise ValueError("sandbox.exec requires a non-empty string command list")

        result = await configured_sandbox.run(
            SandboxRequest(
                command=tuple(raw_command),
                workspace=context.workspace,
                environment=arguments.get("environment"),
            )
        )
        return {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": result.duration_ms,
        }

    async def workspace_read_text(
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        path = _resolve_workspace_path(context.workspace, arguments.get("path"))
        if not path.is_file():
            raise ValueError(f"Workspace file does not exist: {arguments.get('path')}")
        if path.stat().st_size > 2_000_000:
            raise ValueError("Workspace file exceeds the 2 MB read limit")
        return {"path": str(path.relative_to(context.workspace)), "content": path.read_text(encoding="utf-8")}

    async def workspace_list(
        context: ToolExecutionContext,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        directory = _resolve_workspace_path(context.workspace, arguments.get("path", "."))
        if not directory.is_dir():
            raise ValueError(f"Workspace directory does not exist: {arguments.get('path')}")
        entries = sorted(
            (
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                }
                for entry in directory.iterdir()
            ),
            key=lambda item: (item["type"], item["name"].lower()),
        )
        return {"path": str(directory.relative_to(context.workspace)), "entries": entries}

    registry.register(
        ToolDefinition(
            name="workspace.read_text",
            description="Read a UTF-8 text file inside the explicit task workspace.",
            risk_level="R1",
            handler=workspace_read_text,
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="workspace.list",
            description="List entries inside the explicit task workspace.",
            risk_level="R1",
            handler=workspace_list,
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolDefinition(
            name="sandbox.exec",
            description=(
                "Execute an explicit argv command inside an isolated Docker sandbox "
                "with deny-by-default networking and resource limits."
            ),
            risk_level="R2",
            handler=sandbox_exec,
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "environment": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        )
    )
    return registry


def _resolve_workspace_path(workspace: Path, relative_path: Any) -> Path:
    if not isinstance(relative_path, str) or not relative_path or "\x00" in relative_path:
        raise ValueError("Workspace path must be a non-empty string")

    root = workspace.resolve()
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise PermissionError("Workspace path escapes the task workspace")
    return candidate
