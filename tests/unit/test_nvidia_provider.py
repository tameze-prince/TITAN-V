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
                "name": "sandbox.exec",
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
