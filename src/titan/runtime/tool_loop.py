import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from titan.runtime.context import ContextEngine
from titan.runtime.contracts import AgentContract, AgentTaskContext
from titan.runtime.tools import (
    ToolCall,
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutor,
)


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ModelToolTurn:
    response_id: str | None
    text: str
    tool_calls: tuple[ModelToolCall, ...] = ()
    usage: dict[str, Any] = field(default_factory=dict)


class ToolAwareModelProvider(Protocol):
    async def generate_tool_turn(
        self,
        *,
        system_prompt: str,
        user_prompt: str | list[dict[str, Any]],
        tools: list[dict[str, Any]],
        previous_response_id: str | None,
    ) -> ModelToolTurn:
        ...


@dataclass(frozen=True, slots=True)
class ToolLoopPolicy:
    max_steps: int = 8
    max_tool_calls: int = 24


@dataclass(slots=True)
class ToolLoopResult:
    final_text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)


class AgentToolLoop:
    def __init__(
        self,
        *,
        context_engine: ContextEngine | None = None,
        policy: ToolLoopPolicy | None = None,
    ) -> None:
        self.context_engine = context_engine or ContextEngine()
        self.policy = policy or ToolLoopPolicy()

    async def run(
        self,
        *,
        provider: ToolAwareModelProvider,
        contract: AgentContract,
        task: AgentTaskContext,
        workspace,
        tools: tuple[ToolDefinition, ...],
        executor: ToolExecutor,
    ) -> ToolLoopResult:
        frame = self.context_engine.build(
            contract=contract,
            task=task,
            workspace=workspace,
            tools=tools,
        )

        tool_specs = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "strict": tool.strict,
                "parameters": tool.input_schema or {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True,
                },
            }
            for tool in tools
        ]

        first_input: str | list[dict[str, Any]] = frame.user_prompt
        previous_response_id: str | None = None
        history: list[dict[str, Any]] = []
        final_text = ""
        tool_call_count = 0
        usage: dict[str, Any] = {}

        for step in range(self.policy.max_steps):
            turn = await provider.generate_tool_turn(
                system_prompt=frame.system_prompt,
                user_prompt=first_input,
                tools=tool_specs,
                previous_response_id=previous_response_id,
            )
            final_text = turn.text or final_text
            previous_response_id = turn.response_id
            usage = {
                **usage,
                **turn.usage,
            }

            if not turn.tool_calls:
                return ToolLoopResult(
                    final_text=final_text,
                    tool_calls=history,
                    tool_results=[item for item in history if item["kind"] == "tool_result"],
                    usage=usage,
                )

            tool_call_count += len(turn.tool_calls)
            if tool_call_count > self.policy.max_tool_calls:
                raise RuntimeError("Tool loop exceeded the maximum tool-call budget")

            outputs: list[dict[str, Any]] = []
            for call in turn.tool_calls:
                call_record = {
                    "kind": "tool_call",
                    "step": step + 1,
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments": call.arguments,
                }
                history.append(call_record)

                execution_context = ToolExecutionContext(
                    task_id=task.task_id,
                    run_id=task.run_id,
                    project_id=task.project_id,
                    task_risk=task.risk_level,
                    agent_risk_ceiling=contract.risk_ceiling,
                    workspace=workspace,
                )
                try:
                    execution = await executor.execute(
                        ToolCall(name=call.name, arguments=call.arguments),
                        execution_context,
                        allowed_tools=contract.allowed_tools,
                    )
                    result_payload = execution.output
                    result_record = {
                        "kind": "tool_result",
                        "step": step + 1,
                        "call_id": call.call_id,
                        "name": call.name,
                        "status": execution.status,
                        "output": result_payload,
                    }
                    history.append(result_record)
                    outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(result_payload, default=str),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    error_payload = {
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    }
                    result_record = {
                        "kind": "tool_result",
                        "step": step + 1,
                        "call_id": call.call_id,
                        "name": call.name,
                        "status": "FAILED",
                        "output": error_payload,
                    }
                    history.append(result_record)
                    outputs.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.call_id,
                            "output": json.dumps(error_payload),
                        }
                    )

            first_input = outputs

        raise RuntimeError("Tool loop reached the maximum number of steps")

