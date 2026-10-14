from types import SimpleNamespace

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


@pytest.mark.asyncio
async def test_nemotron_tool_call_sends_required_template_flags() -> None:
    from titan.runtime.nvidia_provider import NVIDIAChatCompletionsProvider

    provider = NVIDIAChatCompletionsProvider(
        api_key="test-key",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        base_url="https://example.invalid/v1",
        enable_thinking=False,
    )
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        function = SimpleNamespace(
            name="sandbox_exec",
            arguments='{"command":["python","-V"]}',
        )
        call = SimpleNamespace(id="call-1", function=function)
        message = SimpleNamespace(content="", tool_calls=[call])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=None,
        )

    provider._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=fake_create),
        ),
    )

    turn = await provider.generate_tool_turn(
        system_prompt="Use the supplied tools.",
        user_prompt="Run the Python version command using sandbox.exec.",
        tools=[
            {
                "type": "function",
                "name": "sandbox.exec",
                "description": "Execute a sandbox command",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "array"}},
                    "required": ["command"],
                },
            }
        ],
        previous_response_id=None,
    )

    assert captured["extra_body"]["chat_template_kwargs"] == {
        "enable_thinking": True,
        "force_nonempty_content": True,
    }
    assert captured["tool_choice"] == "required"
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].name == "sandbox.exec"

