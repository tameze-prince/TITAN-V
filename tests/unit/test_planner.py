import pytest

from titan.runtime.capabilities import build_default_capability_registry
from titan.runtime.contracts import AgentContract
from titan.runtime.intent import local_compile_intent
from titan.runtime.planner import (
    CapabilityResolutionError,
    CapabilityResolver,
    TaskGraphPlanner,
    topological_order,
)
from titan.runtime.service import (
    AgentContractRegistry,
    ENGINEERING_AGENT,
    GENERAL_AGENT,
)


def test_capability_resolver_normalizes_and_deduplicates_names() -> None:
    resolver = CapabilityResolver(
        build_default_capability_registry(),
        (
            AgentContract(
                name="general-executor",
                role="General",
                instructions="Execute tasks.",
                capabilities=("analysis", "structured-output"),
            ),
        ),
    )

    result = resolver.resolve(["Structured Output", "analysis", "analysis"])

    assert result.missing == ()
    assert result.requested == ("structured-output", "analysis")
    assert [item.name for item in result.resolved] == [
        "structured-output",
        "analysis",
    ]


def test_capability_resolver_reports_unknown_capabilities() -> None:
    resolver = CapabilityResolver(
        build_default_capability_registry(),
        (),
    )

    result = resolver.resolve(["not-registered"])

    assert result.missing == ("not-registered",)
    with pytest.raises(CapabilityResolutionError):
        resolver.choose_agent(["not-registered"], risk_level="R1")


def test_task_graph_planner_builds_a_dag_with_assignments() -> None:
    runtime_contracts = AgentContractRegistry(
        (GENERAL_AGENT, ENGINEERING_AGENT)
    ).all()
    planner = TaskGraphPlanner(
        build_default_capability_registry(),
        runtime_contracts,
    )

    plan = planner.plan(local_compile_intent("Build a secure web platform."))

    assert plan.version == 1
    assert plan.nodes
    assert len({node.key for node in plan.nodes}) == len(plan.nodes)
    assert {node.agent_name for node in plan.nodes} == {"general-executor"}

    deliverable = next(node for node in plan.nodes if node.key == "deliverable-1")
    research_keys = {
        node.key for node in plan.nodes if node.key.startswith("research-")
    }
    assert set(deliverable.dependencies) == research_keys

    ordered = topological_order(plan.nodes)
    positions = {node.key: index for index, node in enumerate(ordered)}
    for node in ordered:
        for dependency in node.dependencies:
            assert positions[dependency] < positions[node.key]


def test_agent_contract_registry_exposes_deterministic_contracts() -> None:
    registry = AgentContractRegistry(
        (GENERAL_AGENT, ENGINEERING_AGENT)
    )
    names = [contract.name for contract in registry.all()]

    assert names == sorted(names)
    assert "engineering-executor" in names
    assert "general-executor" in names
