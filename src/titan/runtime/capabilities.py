from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    name: str
    description: str
    risk_level: str = "R1"


class CapabilityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, CapabilityDefinition] = {}

    def register(self, capability: CapabilityDefinition) -> None:
        self._items[capability.name] = capability

    def resolve(self, name: str) -> CapabilityDefinition:
        try:
            return self._items[name]
        except KeyError as exc:
            raise KeyError(f"Capability '{name}' is not registered") from exc

    def resolve_many(self, names: tuple[str, ...]) -> tuple[CapabilityDefinition, ...]:
        return tuple(self.resolve(name) for name in names)


def build_default_capability_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDefinition(
            name="analysis",
            description="Analyze task input and produce a structured conclusion.",
            risk_level="R1",
        )
    )
    registry.register(
        CapabilityDefinition(
            name="structured-output",
            description="Produce output that conforms to the requested structured schema.",
            risk_level="R1",
        )
    )
    registry.register(
        CapabilityDefinition(
            name="artifact-write",
            description="Produce a durable artifact candidate from an execution result.",
            risk_level="R1",
        )
    )
    return registry
