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
                "name": "sandbox_x2e_exec",
                "description": "Execute a sandbox command",
                "strict": False,
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

    encoded = NVIDIAChatCompletionsProvider._external_tool_name("workspace.list")
    decoded = NVIDIAChatCompletionsProvider._internal_tool_name(encoded)

    assert encoded == "workspace_x2e_list"
    assert decoded == "workspace.list"
