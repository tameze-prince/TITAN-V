from collections import defaultdict, deque
from dataclasses import dataclass

from titan.runtime.capabilities import CapabilityRegistry
from titan.runtime.contracts import AgentContract
from titan.runtime.planner import CapabilityResolver


@dataclass(frozen=True, slots=True)
class Reassignment:
    task_id: str
    previous_agent: str | None
    new_agent: str
    reason: str


@dataclass(frozen=True, slots=True)
class ReplanDecision:
    failed_task_ids: tuple[str, ...]
    impacted_task_ids: tuple[str, ...]
    reassignments: tuple[Reassignment, ...]
    rationale: str


class AdaptiveReplanner:
    """Analyze failed work and produce a deterministic selective-repair plan."""

    def __init__(
        self,
        capability_registry: CapabilityRegistry,
        contracts: tuple[AgentContract, ...],
    ) -> None:
        self.capability_registry = capability_registry
        self.contracts = contracts

    def analyze(
        self,
        *,
        task_ids: tuple[str, ...],
        dependencies: tuple[tuple[str, tuple[str, ...]], ...],
        failed_task_ids: tuple[str, ...],
        task_metadata: tuple[tuple[str, tuple[str, ...], str, str | None], ...],
    ) -> ReplanDecision:
        task_set = set(task_ids)
        failed = tuple(dict.fromkeys(failed_task_ids))
        unknown_failed = set(failed).difference(task_set)
        if unknown_failed:
            raise ValueError(
                "Failed task list contains unknown tasks: "
                + ", ".join(sorted(unknown_failed))
            )
        if not failed:
            raise ValueError("Adaptive replanning requires at least one failed task")

        dependents: dict[str, set[str]] = defaultdict(set)
        for task_id, dependency_ids in dependencies:
            if task_id not in task_set:
                raise ValueError(f"Dependency references unknown task '{task_id}'")
            for dependency_id in dependency_ids:
                if dependency_id not in task_set:
                    raise ValueError(
                        f"Dependency references unknown task '{dependency_id}'"
                    )
                dependents[dependency_id].add(task_id)

        impacted: set[str] = set(failed)
        queue = deque(failed)
        while queue:
            current = queue.popleft()
            for dependent in sorted(dependents[current]):
                if dependent in impacted:
                    continue
                impacted.add(dependent)
                queue.append(dependent)

        metadata = {
            task_id: (capabilities, risk_level, agent_name)
            for task_id, capabilities, risk_level, agent_name in task_metadata
        }
        reassignments: list[Reassignment] = []

        for task_id in failed:
            item = metadata.get(task_id)
            if item is None:
                continue
            capabilities, risk_level, previous_agent = item
            candidates = tuple(
                contract
                for contract in self.contracts
                if contract.name != previous_agent
            )
            if not candidates:
                continue

            try:
                resolver = CapabilityResolver(self.capability_registry, candidates)
                replacement = resolver.choose_agent(
                    capabilities,
                    risk_level=risk_level,
                )
            except (ValueError, KeyError):
                continue

            if replacement.name == previous_agent:
                continue

            reassignments.append(
                Reassignment(
                    task_id=task_id,
                    previous_agent=previous_agent,
                    new_agent=replacement.name,
                    reason="Alternate compatible agent selected after task failure",
                )
            )

        return ReplanDecision(
            failed_task_ids=failed,
            impacted_task_ids=tuple(
                task_id for task_id in task_ids if task_id in impacted
            ),
            reassignments=tuple(reassignments),
            rationale=(
                "The failed task set was expanded to its downstream dependency "
                "closure. Failed tasks may be reassigned to a compatible alternate "
                "agent; successful unaffected work is preserved for selective "
                "re-execution."
            ),
        )
