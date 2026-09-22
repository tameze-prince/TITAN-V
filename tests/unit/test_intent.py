import pytest

from titan.runtime.intent import IntentCompiler, IntentRepresentation, local_compile_intent
from titan.runtime.providers import LocalStructuredProvider


def test_local_intent_compiler_is_structured() -> None:
    representation = local_compile_intent(
        "Build a web platform for managing engineering projects."
    )

    assert isinstance(representation, IntentRepresentation)
    assert representation.problem.startswith("Build a web platform")
    assert representation.required_capabilities


@pytest.mark.asyncio
async def test_intent_compiler_uses_provider_contract() -> None:
    compiler = IntentCompiler(
        LocalStructuredProvider(),
        "local",
    )

    result = await compiler.compile(
        raw_intent="Create a secure project management platform.",
        project_context={"phase": "discovery"},
    )

    assert result.provider == "local"
    assert result.model == "local"
    assert result.representation.desired_outcome
    assert "analysis" in result.representation.required_capabilities
