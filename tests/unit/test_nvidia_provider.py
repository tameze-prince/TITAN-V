import pytest

from titan.runtime.providers import build_default_provider_router


def test_default_provider_router_registers_nvidia() -> None:
    router = build_default_provider_router(
        nvidia_api_key="test-key",
        nvidia_model="nvidia/nemotron-3-ultra-550b-a55b",
    )

    provider = router.resolve("nvidia:nvidia/nemotron-3-ultra-550b-a55b")

    assert provider.name == "nvidia"


def test_nvidia_tool_schema_is_converted_to_chat_completions_shape() -> None:
    from titan.runtime.nvidia_provider import NVIDIAChatCompletionsProvider

    tools = NVIDIAChatCompletionsProvider._chat_tools(
        [
            {
                "type": "function",
                "name": "sandbox.exec",
                "description": "Execute a sandbox command",
                "strict": False,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "array"},
                    },
                },
            }
        ]
    )

    assert tools == [
        {
            "type": "function",
            "function": {
                "name": "sandbox_exec",
                "description": "Execute a sandbox command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "array"},
                    },
                },
            },
        }
    ]


def test_nvidia_tool_name_round_trip_preserves_titan_name() -> None:
    from titan.runtime.nvidia_provider import NVIDIAChatCompletionsProvider

    tools = [{"name": "workspace.list"}, {"name": "sandbox.exec"}]
    aliases = NVIDIAChatCompletionsProvider._tool_name_map(tools)

    assert aliases == {
        "workspace_list": "workspace.list",
        "sandbox_exec": "sandbox.exec",
    }


def test_nvidia_tool_alias_collisions_are_rejected() -> None:
    from titan.runtime.nvidia_provider import NVIDIAChatCompletionsProvider

    with pytest.raises(ValueError, match="collide after provider aliasing"):
        NVIDIAChatCompletionsProvider._tool_name_map(
            [{"name": "workspace.list"}, {"name": "workspace_list"}]
        )

def test_nvidia_prompt_uses_api_aliases_consistently() -> None:
    from titan.runtime.nvidia_provider import NVIDIAChatCompletionsProvider

    tools = [{"name": "workspace.list"}, {"name": "sandbox.exec"}]
    aliases = NVIDIAChatCompletionsProvider._tool_name_map(tools)
    prompt = '{"name": "workspace.list"} Use sandbox.exec.'

    normalized = NVIDIAChatCompletionsProvider._align_prompt_tool_names(
        prompt, aliases
    )

    assert normalized == '{"name": "workspace_list"} Use sandbox_exec.'
