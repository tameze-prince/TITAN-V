from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    risk_level: str = "R1"
    handler: ToolHandler | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._items:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._items[tool.name] = tool

    def resolve(self, name: str) -> ToolDefinition:
        try:
            return self._items[name]
        except KeyError as exc:
            raise KeyError(f"Tool '{name}' is not registered") from exc

    def resolve_many(self, names: tuple[str, ...]) -> tuple[ToolDefinition, ...]:
        return tuple(self.resolve(name) for name in names)


def build_default_tool_registry() -> ToolRegistry:
    return ToolRegistry()
