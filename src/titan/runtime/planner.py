from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, Field

from titan.runtime.capabilities import CapabilityDefinition, CapabilityRegistry
from titan.runtime.contracts import AgentContract


RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


class CapabilityResolutionError(ValueError):
    def __init__(self, missing: tuple[str, ...]) -> None:
        self.missing = missing
        super().__init__(
            "Planner cannot resolve required capabilities: " + ", ".join(missing)
        )


@dataclass(frozen=True, slots=True)
class CapabilityResolution:
    requested: tuple[str, ...]
    resolved: tuple[CapabilityDefinition, ...]
    missing: tuple[str, ...]

    @property
    def maximum_risk_level(self) -> str:
        if not self.resolved:
            return "R0"
        return max(
            (item.risk_level for item in self.resolved),
            key=lambda value: RISK_ORDER[value],
        )


class CapabilityResolver:
    """Resolve intent capabilities and map them to compatible agent contracts."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        contracts: Sequence[AgentContract],
    ) -> None:
        self.registry = registry
        self.contracts = tuple(contracts)

    @staticmethod
    def normalize(name: str) -> str:
        return "-".join(name.strip().lower().replace("_", " ").split())

    def resolve(self, names: Iterable[str]) -> CapabilityResolution:
        requested: list[str] = []
        resolved: list[CapabilityDefinition] = []
        missing: list[str] = []
        seen: set[str] = set()

        for raw_name in names:
            name = self.normalize(raw_name)
            if not name or name in seen:
                continue
            seen.add(name)
            requested.append(name)
            try:
                resolved.append(self.registry.resolve(name))
            except KeyError:
                missing.append(name)

        return CapabilityResolution(
            requested=tuple(requested),
            resolved=tuple(resolved),
            missing=tuple(missing),
        )

    def choose_agent(
        self,
        capabilities: Iterable[str],
        *,
        risk_level: str,
    ) -> AgentContract:
        if risk_level not in RISK_ORDER:
            raise ValueError(f"Unsupported risk level: {risk_level}")

        required = {self.normalize(item) for item in capabilities if item.strip()}
        candidates: list[AgentContract] = []

        for contract in self.contracts:
            if RISK_ORDER[contract.risk_ceiling] < RISK_ORDER[risk_level]:
                continue

            available = {self.normalize(item) for item in contract.capabilities}
            if required.issubset(available):
                candidates.append(contract)

        if not candidates:
            raise CapabilityResolutionError(tuple(sorted(required)))

        def score(contract: AgentContract) -> tuple[int, int, str]:
            available = {self.normalize(item) for item in contract.capabilities}
            extra_capabilities = len(available.difference(required))
            generalist_penalty = 0 if contract.name == "general-executor" else 1
            return extra_capabilities, generalist_penalty, contract.name

        return min(candidates, key=score)


class TaskPlanNode(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=255)
    objective: str = Field(min_length=1, max_length=10_000)
    required_capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    agent_name: str = Field(min_length=1, max_length=120)
    risk_level: str = Field(default="R1", pattern=r"^R[0-4]$")
    approval_requirement: str = "NONE"
    approval_quorum: int = Field(default=1, ge=1, le=10)
    position: int = Field(ge=0)


class TaskGraphPlan(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    objective: str = Field(min_length=1, max_length=10_000)
    version: int = Field(default=1, ge=1)
    nodes: tuple[TaskPlanNode, ...]
    unknowns: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    rationale: str = Field(min_length=1)


class TaskGraphPlanner:
    """Deterministically transform compiled intent into an executable DAG."""

    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        contracts: Sequence[AgentContract],
    ) -> None:
        self.capability_resolver = CapabilityResolver(capability_registry, contracts)

    def plan(self, intent, *, version: int = 1) -> TaskGraphPlan:
        capability_resolution = self.capability_resolver.resolve(
            intent.required_capabilities
        )
        if capability_resolution.missing:
            raise CapabilityResolutionError(capability_resolution.missing)

        base_capabilities = tuple(
            item.name for item in capability_resolution.resolved
        )
        nodes: list[TaskPlanNode] = []

        research_questions = self._unique_nonempty(intent.research_questions)
        deliverables = self._unique_nonempty(intent.candidate_deliverables)

        for index, question in enumerate(research_questions):
            capabilities = self._ensure_analysis_capability(base_capabilities)
            agent = self.capability_resolver.choose_agent(
                capabilities,
                risk_level="R1",
            )
            nodes.append(
                TaskPlanNode(
                    key=f"research-{index + 1}",
                    title=f"Research: {question[:210]}",
                    objective=question,
                    required_capabilities=capabilities,
                    agent_name=agent.name,
                    position=len(nodes),
                    risk_level="R1",
                )
            )

        research_keys = tuple(node.key for node in nodes)

        if not deliverables:
            deliverables = (intent.desired_outcome or intent.problem or "Execute the requested objective.",)

        deliverable_capabilities = self._ensure_capabilities(
            base_capabilities,
            ("artifact-write",),
        )
        deliverable_risk = self._risk_for_capabilities(deliverable_capabilities)
        for index, deliverable in enumerate(deliverables):
            agent = self.capability_resolver.choose_agent(
                deliverable_capabilities,
                risk_level=deliverable_risk,
            )
            nodes.append(
                TaskPlanNode(
                    key=f"deliverable-{index + 1}",
                    title=f"Deliver: {deliverable[:210]}",
                    objective=deliverable,
                    required_capabilities=deliverable_capabilities,
                    dependencies=research_keys,
                    agent_name=agent.name,
                    position=len(nodes),
                    risk_level=deliverable_risk,
                )
            )

        if len(nodes) > 1:
            synthesis_capabilities = self._ensure_capabilities(
                base_capabilities,
                ("artifact-write",),
            )
            synthesis_risk = self._risk_for_capabilities(synthesis_capabilities)
            agent = self.capability_resolver.choose_agent(
                synthesis_capabilities,
                risk_level=synthesis_risk,
            )
            nodes.append(
                TaskPlanNode(
                    key="synthesis",
                    title="Synthesize and validate the planned deliverables",
                    objective=(
                        "Review the outputs of the preceding tasks, resolve "
                        "inconsistencies, and produce the coherent final result."
                    ),
                    required_capabilities=synthesis_capabilities,
                    dependencies=tuple(node.key for node in nodes),
                    agent_name=agent.name,
                    position=len(nodes),
                    risk_level=synthesis_risk,
                )
            )

        self._validate_dag(nodes)

        return TaskGraphPlan(
            name=f"Execution Plan v{version}",
            objective=intent.desired_outcome or intent.problem or "Execute project intent.",
            version=version,
            nodes=tuple(nodes),
            unknowns=tuple(intent.unknowns),
            constraints=tuple(intent.constraints),
            risks=tuple(intent.risks),
            rationale=(
                "Generated from the compiled intent using registered capabilities, "
                "risk-aware agent assignment, explicit dependencies, and a "
                "deterministic topological order."
            ),
        )

    @staticmethod
    def _unique_nonempty(values: Iterable[str]) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            result.append(cleaned)
        return tuple(result)

    @staticmethod
    def _ensure_analysis_capability(capabilities: tuple[str, ...]) -> tuple[str, ...]:
        return TaskGraphPlanner._ensure_capabilities(capabilities, ("analysis",))

    def _risk_for_capabilities(self, capabilities: tuple[str, ...]) -> str:
        return self.capability_resolver.resolve(capabilities).maximum_risk_level

    @staticmethod
    def _ensure_capabilities(
        capabilities: tuple[str, ...],
        required: tuple[str, ...],
    ) -> tuple[str, ...]:
        result = list(capabilities)
        for name in required:
            if name not in result:
                result.append(name)
        return tuple(result)

    @staticmethod
    def _validate_dag(nodes: Sequence[TaskPlanNode]) -> None:
        by_key = {node.key: node for node in nodes}
        if len(by_key) != len(nodes):
            raise ValueError("Task graph contains duplicate task keys")

        for node in nodes:
            missing = set(node.dependencies).difference(by_key)
            if missing:
                raise ValueError(
                    f"Task '{node.key}' depends on unknown tasks: {', '.join(sorted(missing))}"
                )

        state: dict[str, int] = {key: 0 for key in by_key}

        def visit(key: str) -> None:
            if state[key] == 1:
                raise ValueError("Task graph contains a dependency cycle")
            if state[key] == 2:
                return
            state[key] = 1
            for dependency in by_key[key].dependencies:
                visit(dependency)
            state[key] = 2

        for key in by_key:
            visit(key)


def topological_order(
    nodes: Sequence[TaskPlanNode],
) -> tuple[TaskPlanNode, ...]:
    by_key = {node.key: node for node in nodes}
    indegree = {node.key: len(node.dependencies) for node in nodes}
    dependents: dict[str, list[str]] = {node.key: [] for node in nodes}

    for node in nodes:
        for dependency in node.dependencies:
            dependents[dependency].append(node.key)

    ready = sorted(
        (key for key, degree in indegree.items() if degree == 0),
        key=lambda key: by_key[key].position,
    )
    ordered: list[TaskPlanNode] = []

    while ready:
        key = ready.pop(0)
        ordered.append(by_key[key])
        for dependent in sorted(
            dependents[key],
            key=lambda item: by_key[item].position,
        ):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
        ready.sort(key=lambda item: by_key[item].position)

    if len(ordered) != len(nodes):
        raise ValueError("Task graph contains a dependency cycle")

    return tuple(ordered)
