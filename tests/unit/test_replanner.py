from titan.runtime.capabilities import (
    CapabilityDefinition,
    CapabilityRegistry,
)
from titan.runtime.contracts import AgentContract
from titan.runtime.replanner import AdaptiveReplanner


def build_registry() -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        CapabilityDefinition(
            name="analysis",
            description="Analyze task input.",
            risk_level="R1",
        )
    )
    registry.register(
        CapabilityDefinition(
            name="structured-output",
            description="Produce structured output.",
            risk_level="R1",
        )
    )
    registry.register(
        CapabilityDefinition(
            name="artifact-write",
            description="Write durable artifacts.",
            risk_level="R1",
        )
    )
    return registry


def test_adaptive_replanner_expands_failure_to_downstream_closure() -> None:
    contracts = (
        AgentContract(
            name="general-executor",
            role="General",
            instructions="Execute tasks.",
            capabilities=("analysis", "structured-output", "artifact-write"),
            risk_ceiling="R1",
        ),
        AgentContract(
            name="engineering-executor",
            role="Engineering",
            instructions="Execute engineering tasks.",
            capabilities=("analysis", "structured-output", "artifact-write"),
            risk_ceiling="R2",
        ),
    )
    replanner = AdaptiveReplanner(build_registry(), contracts)

    decision = replanner.analyze(
        task_ids=("a", "b", "c"),
        dependencies=(
            ("b", ("a",)),
        ),
        failed_task_ids=("a",),
        task_metadata=(
            ("a", ("analysis", "structured-output", "artifact-write"), "R1", "general-executor"),
            ("b", ("analysis", "structured-output", "artifact-write"), "R1", "general-executor"),
            ("c", ("analysis", "structured-output", "artifact-write"), "R1", "general-executor"),
        ),
    )

    assert decision.failed_task_ids == ("a",)
    assert decision.impacted_task_ids == ("a", "b")
    assert decision.reassignments[0].task_id == "a"
    assert decision.reassignments[0].previous_agent == "general-executor"
    assert decision.reassignments[0].new_agent == "engineering-executor"


def test_adaptive_replanner_requires_a_failed_task() -> None:
    replanner = AdaptiveReplanner(
        build_registry(),
        (
            AgentContract(
                name="general-executor",
                role="General",
                instructions="Execute tasks.",
            ),
        ),
    )

    try:
        replanner.analyze(
            task_ids=("a",),
            dependencies=(),
            failed_task_ids=(),
            task_metadata=(
                ("a", ("analysis",), "R1", "general-executor"),
            ),
        )
    except ValueError as exc:
        assert "at least one failed task" in str(exc)
    else:
        raise AssertionError("Expected adaptive replanning to reject empty failure input")
