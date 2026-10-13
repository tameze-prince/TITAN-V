import json
import re
from typing import Any
from uuid import uuid4

from openai import AsyncOpenAI

from titan.runtime.providers import ModelProvider, ModelRequest, ModelResponse


class NVIDIAChatCompletionsProvider(ModelProvider):
    name = "nvidia"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = 60.0,
        max_output_tokens: int = 16_000,
        tool_max_output_tokens: int = 2_048,
        temperature: float = 1.0,
        top_p: float = 0.95,
        enable_thinking: bool = True,
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._tool_max_output_tokens = tool_max_output_tokens
        self._temperature = temperature
        self._top_p = top_p
        self._enable_thinking = enable_thinking
        self._conversations: dict[str, dict[str, Any]] = {}
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    @staticmethod
    def _requested_model(request_model: str, default_model: str) -> str:
        if request_model.startswith("nvidia:"):
            return request_model.split(":", 1)[1]
        return default_model

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        payload = content.strip()
        try:
            value = json.loads(payload)
        except json.JSONDecodeError:
            start = payload.find("{")
            end = payload.rfind("}")
            if start < 0 or end <= start:
                raise ValueError("NVIDIA response did not contain valid JSON") from None
            value = json.loads(payload[start : end + 1])
        if not isinstance(value, dict):
            raise TypeError("NVIDIA structured response must be a JSON object")
        return value

    @staticmethod
    def _usage(response: Any) -> dict[str, Any]:
        if response.usage is None:
            return {}
        return response.usage.model_dump(mode="json")

    async def generate(
        self,
        request: ModelRequest,
        output_model: type[Any],
    ) -> ModelResponse:
        model = self._requested_model(request.model, self._model)
        response = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {
                    "role": "user",
                    "content": (
                        request.user_prompt
                        + "\n\nReturn ONLY valid JSON matching this schema:\n"
                        + json.dumps(
                            output_model.model_json_schema(),
                            separators=(",", ":"),
                        )
                    ),
                },
            ],
            max_tokens=self._max_output_tokens,
            temperature=0.0,
            top_p=self._top_p,
            response_format={"type": "json_object"},
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": False,
                    "force_nonempty_content": True,
                }
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("NVIDIA response did not contain structured content")
        parsed = output_model.model_validate(self._parse_json(content))
        return ModelResponse(
            provider=self.name,
            model=model,
            parsed=parsed,
            usage=self._usage(response),
        )

    @staticmethod
    def _external_tool_name(name: str) -> str:
        """Return an API-compatible alias for an internal TITAN tool name."""
        alias = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
        if not alias:
            raise ValueError("Tool name cannot be converted to an API alias")
        return alias

    @classmethod
    def _tool_name_map(cls, tools: list[dict[str, Any]]) -> dict[str, str]:
        """Map API-safe names back to the exact registered TITAN tool names."""
        aliases: dict[str, str] = {}
        for tool in tools:
            internal_name = tool["name"]
            external_name = cls._external_tool_name(internal_name)
            existing = aliases.get(external_name)
            if existing is not None and existing != internal_name:
                raise ValueError(
                    f"TITAN tool names collide after provider aliasing: "
                    f"{existing!r} and {internal_name!r}"
                )
            aliases[external_name] = internal_name
        return aliases

    @classmethod
    def _align_prompt_tool_names(
        cls,
        prompt: str,
        tool_name_map: dict[str, str],
    ) -> str:
        """Use the same callable aliases in prompt text and API schemas."""
        for external_name, internal_name in sorted(
            tool_name_map.items(),
            key=lambda item: len(item[1]),
            reverse=True,
        ):
            prompt = prompt.replace(internal_name, external_name)
        return prompt

    @staticmethod
    def _internal_tool_name(name: str) -> str:
        import re

        def decode(match: re.Match[str]) -> str:
            return chr(int(match.group(1), 16))

        return re.sub(r"_x([0-9a-f]+)_", decode, name)

    @classmethod
    def _chat_tools(cls, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": cls._external_tool_name(tool["name"]),
                    "description": tool.get("description", ""),
                    "parameters": tool.get(
                        "parameters",
                        {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": True,
                        },
                    ),
                },
            }
            for tool in tools
        ]

    async def generate_tool_turn(
        self,
        *,
        system_prompt: str,
        user_prompt: str | list[dict[str, Any]],
        tools: list[dict[str, Any]],
        previous_response_id: str | None,
    ):
        from titan.runtime.tool_loop import ModelToolCall, ModelToolTurn

        tool_name_map = self._tool_name_map(tools)

        if previous_response_id is None:
            conversation_id = uuid4().hex
            normalized_system = self._align_prompt_tool_names(
                system_prompt, tool_name_map
            )
            if isinstance(user_prompt, str):
                normalized_user = self._align_prompt_tool_names(
                    user_prompt, tool_name_map
                )
            else:
                normalized_user = user_prompt
            normalized_system += (
                "\n\nTool protocol: invoke the native function tools provided "
                "with this request. Do not write a tool call as JSON or text in "
                "the assistant response; text that describes a tool call is not "
                "executed. Use the callable tool names exactly as provided."
            )
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": normalized_system},
                {"role": "user", "content": normalized_user},
            ]
            state = {"messages": messages, "pending_assistant": None}
            self._conversations[conversation_id] = state
        else:
            state = self._conversations.get(previous_response_id)
            if state is None:
                raise ValueError("NVIDIA tool-loop continuation state is unavailable")
            messages = state["messages"]
            pending = state.get("pending_assistant")
            pending_names: dict[str, str] = {}
            if pending is not None:
                for pending_call in pending.get("tool_calls", []):
                    function = pending_call.get("function", {})
                    call_id = pending_call.get("id")
                    function_name = function.get("name")
                    if isinstance(call_id, str) and isinstance(function_name, str):
                        pending_names[call_id] = function_name
                messages.append(pending)
            if not isinstance(user_prompt, list):
                raise TypeError("NVIDIA continuation expects tool results")
            for item in user_prompt:
                if item.get("type") == "function_call_output":
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": item["call_id"],
                        "content": item["output"],
                    }
                    function_name = pending_names.get(item["call_id"])
                    if function_name:
                        tool_message["name"] = function_name
                    messages.append(tool_message)
            state["pending_assistant"] = None
            conversation_id = previous_response_id

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=self._chat_tools(tools),
            tool_choice="required" if previous_response_id is None else "auto",
            max_tokens=self._tool_max_output_tokens,
            temperature=self._temperature,
            top_p=self._top_p,
            extra_body={
                "chat_template_kwargs": {
                    "enable_thinking": self._enable_thinking,
                    "force_nonempty_content": True,
                }
            },
        )

        message = response.choices[0].message
        tool_calls = []
        pending_calls = []
        for call in message.tool_calls or []:
            arguments = json.loads(call.function.arguments or "{}")
            if not isinstance(arguments, dict):
                raise TypeError("NVIDIA tool arguments must be a JSON object")
            internal_name = tool_name_map.get(call.function.name)
            if internal_name is None:
                raise ValueError(
                    "NVIDIA returned a call for an unregistered tool alias: "
                    f"{call.function.name!r}"
                )
            tool_calls.append(
                ModelToolCall(
                    call_id=call.id,
                    name=internal_name,
                    arguments=arguments,
                )
            )
            pending_calls.append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments or "{}",
                    },
                }
            )

        if pending_calls:
            state["pending_assistant"] = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": pending_calls,
            }
            response_id = conversation_id
        else:
            messages.append({"role": "assistant", "content": message.content or ""})
            self._conversations.pop(conversation_id, None)
            response_id = None

        return ModelToolTurn(
            response_id=response_id,
            text=message.content or "",
            tool_calls=tuple(tool_calls),
            usage=self._usage(response),
        )
