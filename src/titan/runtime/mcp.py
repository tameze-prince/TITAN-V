from dataclasses import dataclass
from typing import Any, Protocol

from titan.runtime.tools import ToolDefinition, ToolRegistry


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    name: str
    url: str
    tool_allowlist: tuple[str, ...] = ()
    default_risk: str = "R2"


class MCPClientProtocol(Protocol):
    async def list_tools(self) -> Any: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class MCPToolProvider:
    def __init__(
        self,
        config: MCPServerConfig,
        *,
        client_factory: Any,
    ) -> None:
        self.config = config
        self._client_factory = client_factory

    async def list_remote_tools(self) -> tuple[dict[str, str], ...]:
        async with self._client_factory(self.config.url) as client:
            result = await client.list_tools()
            tools = []
            for tool in result.tools:
                if self.config.tool_allowlist and tool.name not in self.config.tool_allowlist:
                    continue
                tools.append(
                    {
                        "name": f"mcp.{self.config.name}.{tool.name}",
                        "remote_name": tool.name,
                        "description": getattr(tool, "description", "") or "",
                    }
                )
            return tuple(tools)

    async def register_tools(self, registry: ToolRegistry) -> tuple[str, ...]:
        remote_tools = await self.list_remote_tools()
        registered: list[str] = []

        for remote in remote_tools:
            async def handler(context, arguments, remote_name=remote["remote_name"]):
                async with self._client_factory(self.config.url) as client:
                    result = await client.call_tool(remote_name, arguments)
                    return _serialize_mcp_result(result)

            name = remote["name"]
            registry.register(
                ToolDefinition(
                    name=name,
                    description=remote["description"] or f"MCP tool {remote['remote_name']}",
                    risk_level=self.config.default_risk,
                    handler=handler,
                )
            )
            registered.append(name)

        return tuple(registered)


def _serialize_mcp_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return {
            "structured_content": structured,
            "is_error": bool(getattr(result, "is_error", False)),
        }

    content = getattr(result, "content", [])
    serialized = []
    for item in content:
        if hasattr(item, "model_dump"):
            serialized.append(item.model_dump(mode="json"))
        else:
            serialized.append(str(item))

    return {
        "content": serialized,
        "is_error": bool(getattr(result, "is_error", False)),
    }
