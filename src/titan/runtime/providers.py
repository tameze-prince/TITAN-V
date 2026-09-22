from abc import ABC, abstractmethod
import json
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field


class ModelRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    model: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    provider: str
    model: str
    parsed: BaseModel
    usage: dict[str, Any] = Field(default_factory=dict)


class ModelProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        request: ModelRequest,
        output_model: type[BaseModel],
    ) -> ModelResponse:
        raise NotImplementedError


class LocalStructuredProvider(ModelProvider):
    name = "local"

    async def generate(
        self,
        request: ModelRequest,
        output_model: type[BaseModel],
    ) -> ModelResponse:
        if output_model.__name__ != "AgentModelOutput":
            raise TypeError("Local provider only supports AgentModelOutput")

        from titan.runtime.contracts import AgentModelOutput

        start = perf_counter()
        result = AgentModelOutput(
            summary=f"Local execution completed for: {request.user_prompt.splitlines()[0][:200]}",
            result={
                "provider_mode": "local",
                "model": request.model,
                "objective": request.metadata.get("objective", request.user_prompt),
            },
            artifact_markdown=(
                "# Agent Execution\n\n"
                f"## Objective\n{request.metadata.get('objective', request.user_prompt)}\n\n"
                "## Summary\n"
                "Execution was handled by the deterministic local provider.\n"
            ),
        )
        elapsed_ms = int((perf_counter() - start) * 1000)
        return ModelResponse(
            provider=self.name,
            model=request.model,
            parsed=result,
            usage={"elapsed_ms": elapsed_ms, "mode": "deterministic"},
        )

    async def generate_tool_turn(
        self,
        *,
        system_prompt: str,
        user_prompt: str | list[dict[str, Any]],
        tools: list[dict[str, Any]],
        previous_response_id: str | None,
    ):
        from titan.runtime.tool_loop import ModelToolTurn

        return ModelToolTurn(
            response_id=previous_response_id or "local-response",
            text=f"Local tool-loop execution completed for: "
            f"{user_prompt if isinstance(user_prompt, str) else 'tool results'}",
            tool_calls=(),
        )


class OpenAIResponsesProvider(ModelProvider):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._model = model
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

    async def generate(
        self,
        request: ModelRequest,
        output_model: type[BaseModel],
    ) -> ModelResponse:
        response = await self._client.responses.parse(
            model=self._model,
            input=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            text_format=output_model,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise ValueError("OpenAI response did not contain a structured parsed result")

        usage: dict[str, Any] = {}
        if response.usage is not None:
            usage = response.usage.model_dump(mode="json")

        return ModelResponse(
            provider=self.name,
            model=self._model,
            parsed=parsed,
            usage=usage,
        )

    async def generate_tool_turn(
        self,
        *,
        system_prompt: str,
        user_prompt: str | list[dict[str, Any]],
        tools: list[dict[str, Any]],
        previous_response_id: str | None,
    ):
        from titan.runtime.tool_loop import ModelToolCall, ModelToolTurn

        if previous_response_id is None:
            input_payload: str | list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        else:
            input_payload = user_prompt

        response = await self._client.responses.create(
            model=self._model,
            input=input_payload,
            previous_response_id=previous_response_id,
            tools=tools,
            tool_choice="auto",
        )

        tool_calls: list[ModelToolCall] = []
        for item in response.output:
            if getattr(item, "type", None) != "function_call":
                continue

            arguments_raw = getattr(item, "arguments", "{}")
            arguments = json.loads(arguments_raw)
            if not isinstance(arguments, dict):
                raise TypeError("Model tool arguments must be a JSON object")

            call_id = getattr(item, "call_id", None)
            name = getattr(item, "name", None)
            if not isinstance(call_id, str) or not isinstance(name, str):
                raise TypeError("Model function call is missing call_id or name")

            tool_calls.append(
                ModelToolCall(
                    call_id=call_id,
                    name=name,
                    arguments=arguments,
                )
            )

        return ModelToolTurn(
            response_id=response.id,
            text=response.output_text or "",
            tool_calls=tuple(tool_calls),
        )


class ProviderRouter:
    def __init__(self, providers: dict[str, ModelProvider] | None = None) -> None:
        self._providers = providers or {}

    def register(self, provider: ModelProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(f"Provider '{provider.name}' is already registered")
        self._providers[provider.name] = provider

    def resolve(self, model: str) -> ModelProvider:
        provider_name = model.split(":", 1)[0]
        try:
            return self._providers[provider_name]
        except KeyError as exc:
            raise KeyError(f"Model provider '{provider_name}' is not registered") from exc


def build_default_provider_router(
    *,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-5",
    openai_base_url: str | None = None,
) -> ProviderRouter:
    router = ProviderRouter()
    router.register(LocalStructuredProvider())
    if openai_api_key:
        router.register(
            OpenAIResponsesProvider(
                api_key=openai_api_key,
                model=openai_model,
                base_url=openai_base_url,
            )
        )
    return router
