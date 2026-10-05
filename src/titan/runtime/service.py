from dataclasses import replace
from pathlib import Path
from time import perf_counter

from titan.config import settings
from titan.runtime.capabilities import build_default_capability_registry
from titan.runtime.contracts import (
    AgentContract,
    AgentExecutionResult,
    AgentModelOutput,
    AgentTaskContext,
)
from titan.runtime.evaluation import evaluate_execution
from titan.runtime.governance import GovernanceEngine
from titan.runtime.tool_loop import AgentToolLoop
from titan.runtime.policies import RuntimePolicy
from titan.runtime.model_router import ModelBudget, ModelRoute, ModelRouter, ModelSelectionRequest
from titan.runtime.repair import AgentEvaluationFailure, RepairPlanner, RepairPolicy
from titan.runtime.providers import ModelRequest, build_default_provider_router
from titan.runtime.sandbox import DockerSandbox, SandboxPolicy
from titan.runtime.tools import (
    ToolCall,
    ToolExecutionContext,
    ToolExecutionResult,
    ToolExecutor,
    build_default_tool_registry,
)
from titan.runtime.workspace import WorkspaceManager


ENGINEERING_AGENT = AgentContract(
    name="engineering-executor",
    role="Engineering Task Executor",
    instructions=(
        "Inspect the assigned engineering task, use only explicitly allowed tools, "
        "and return structured evidence of the work performed."
    ),
    capabilities=(
        "analysis",
        "structured-output",
        "artifact-write",
        "software-engineering",
    ),
    allowed_tools=("workspace.list", "workspace.read_text", "sandbox.exec"),
    risk_ceiling="R2",
    max_concurrency=settings.engineering_agent_max_concurrency,
    model=(
        "openai:" + settings.openai_model
        if settings.model_provider == "openai" and settings.openai_api_key
        else (
            "nvidia:" + settings.nvidia_model
            if settings.model_provider == "nvidia" and settings.nvidia_api_key
            else "local"
        )
    ),
)


GENERAL_AGENT = AgentContract(
    name="general-executor",
    role="General Task Executor",
    instructions=(
        "Execute the assigned task faithfully. "
        "Return a concise summary, structured result data, and a useful artifact."
    ),
    capabilities=("analysis", "structured-output", "artifact-write"),
    max_concurrency=settings.general_agent_max_concurrency,
    model=(
        "openai:" + settings.openai_model
        if settings.model_provider == "openai" and settings.openai_api_key
        else (
            "nvidia:" + settings.nvidia_model
            if settings.model_provider == "nvidia" and settings.nvidia_api_key
            else "local"
        )
    ),
    risk_ceiling="R1",
)


class AgentContractRegistry:
    def __init__(self, contracts: tuple[AgentContract, ...] = ()) -> None:
        self._contracts = {contract.name: contract for contract in contracts}

    def register(self, contract: AgentContract) -> None:
        if contract.name in self._contracts:
            raise ValueError(f"Agent contract '{contract.name}' already exists")
        self._contracts[contract.name] = contract

    def resolve(self, name: str) -> AgentContract:
        try:
            return self._contracts[name]
        except KeyError as exc:
            raise KeyError(f"Agent contract '{name}' is not registered") from exc

    def all(self) -> tuple[AgentContract, ...]:
        return tuple(
            self._contracts[name]
            for name in sorted(self._contracts)
        )


class AgentRuntime:
    def __init__(
        self,
        *,
        contracts: AgentContractRegistry | None = None,
        capabilities=None,
        providers=None,
        tools=None,
        policy: RuntimePolicy | None = None,
    ) -> None:
        self.contracts = contracts or AgentContractRegistry((GENERAL_AGENT, ENGINEERING_AGENT))
        self.capabilities = capabilities or build_default_capability_registry()
        self.providers = providers or build_default_provider_router(
            openai_api_key=settings.openai_api_key,
            openai_model=settings.openai_model,
            openai_base_url=settings.openai_base_url,
            nvidia_api_key=settings.nvidia_api_key,
            nvidia_model=settings.nvidia_model,
            nvidia_base_url=settings.nvidia_base_url,
            nvidia_max_output_tokens=settings.nvidia_max_output_tokens,
            nvidia_temperature=settings.nvidia_temperature,
            nvidia_top_p=settings.nvidia_top_p,
            nvidia_enable_thinking=settings.nvidia_enable_thinking,
        )
        self.model_router = ModelRouter(self.providers)
        self.model_router.register(
            ModelRoute(
                name="local-default",
                provider="local",
                model="local",
                quality_tier=1,
                priority=10,
            )
        )
        if settings.openai_api_key:
            self.model_router.register(
                ModelRoute(
                    name=f"openai-{settings.openai_model}",
                    provider="openai",
                    model=f"openai:{settings.openai_model}",
                    quality_tier=2,
                    priority=20,
                    input_cost_per_1k=settings.openai_input_cost_per_1k,
                    output_cost_per_1k=settings.openai_output_cost_per_1k,
                )
            )
        if settings.nvidia_api_key:
            self.model_router.register(
                ModelRoute(
                    name=f"nvidia-{settings.nvidia_model}",
                    provider="nvidia",
                    model=f"nvidia:{settings.nvidia_model}",
                    quality_tier=2,
                    priority=20,
                )
            )
        self.policy = policy or RuntimePolicy()
        self.governance = GovernanceEngine()
        self.tools = tools or build_default_tool_registry(
            sandbox=DockerSandbox(
                SandboxPolicy(
                    image=settings.sandbox_image,
                    network=settings.sandbox_network,
                    memory=settings.sandbox_memory,
                    cpus=settings.sandbox_cpus,
                    pids_limit=settings.sandbox_pids_limit,
                    timeout_seconds=settings.sandbox_timeout_seconds,
                )
            )
        )
        self.tool_executor = ToolExecutor(self.tools, policy=self.policy)
        self.workspace_manager = WorkspaceManager(settings.workspace_root)
        self.tool_loop = AgentToolLoop()
        self.repair_policy = RepairPolicy(max_attempts=settings.repair_max_attempts)
        self.repair_planner = RepairPlanner()

    async def execute_tool(
        self,
        call: ToolCall,
        context: AgentTaskContext,
        workspace: Path | None = None,
        *,
        agent_name: str = "general-executor",
    ) -> ToolExecutionResult:
        contract = self.contracts.resolve(agent_name)
        capabilities = self.capabilities.resolve_many(contract.capabilities)
        decision = self.policy.check(
            task_risk=context.risk_level,
            agent_risk_ceiling=contract.risk_ceiling,
            requested_capabilities=contract.capabilities,
            requested_tools=contract.allowed_tools,
            registered_capabilities=tuple(item.name for item in capabilities),
            allowed_tools=contract.allowed_tools,
        )
        governance = self.governance.decide(
            (
                self.governance.from_policy_decision(
                    policy="runtime",
                    decision=decision,
                ),
            )
        )
        if not governance.allowed:
            raise PermissionError(governance.reason)

        resolved_workspace = (
            workspace.resolve()
            if workspace is not None
            else self.workspace_manager.ensure(
                context.project_id,
                context.task_id,
            ).root
        )

        return await self.tool_executor.execute(
            call,
            ToolExecutionContext(
                task_id=context.task_id,
                run_id=context.run_id,
                project_id=context.project_id,
                task_risk=context.risk_level,
                agent_risk_ceiling=contract.risk_ceiling,
                workspace=resolved_workspace,
            ),
            allowed_tools=contract.allowed_tools,
        )

    async def execute(
        self,
        context: AgentTaskContext,
        *,
        agent_name: str = "general-executor",
    ) -> AgentExecutionResult:
        contract = self.contracts.resolve(agent_name)
        capabilities = self.capabilities.resolve_many(contract.capabilities)
        tool_names = contract.allowed_tools
        self.tools.resolve_many(tool_names)

        decision = self.policy.check(
            task_risk=context.risk_level,
            agent_risk_ceiling=contract.risk_ceiling,
            requested_capabilities=contract.capabilities,
            requested_tools=tool_names,
            registered_capabilities=tuple(item.name for item in capabilities),
            allowed_tools=tool_names,
        )

        budget = ModelBudget(
            max_input_tokens=settings.model_max_input_tokens,
            max_output_tokens=settings.model_max_output_tokens,
            max_cost=settings.model_max_cost,
        )
        selection = self.model_router.select(
            ModelSelectionRequest(
                preferred_model=contract.model,
                minimum_quality_tier=contract.minimum_quality_tier,
                budget=budget,
            )
        )

        governance = self.governance.decide_runtime(
            runtime_policy=decision,
            selection=selection,
            minimum_quality_tier=contract.minimum_quality_tier,
            budget=budget,
        )
        if not governance.allowed:
            raise PermissionError(governance.reason)
        provider = selection.provider
        started = perf_counter()
        repair_context = dict(context.inputs)

        for attempt in range(1, self.repair_policy.max_attempts + 2):
            execution_context = replace(context, inputs=repair_context)
            prompt = (
                f"Task title: {execution_context.title}\n"
                f"Task objective: {execution_context.objective}\n"
                f"Risk level: {execution_context.risk_level}\n"
                f"Additional inputs: {execution_context.inputs}\n"
            )
            request = ModelRequest(
                system_prompt=contract.instructions,
                user_prompt=prompt,
                model=selection.route.model,
                metadata={
                    "task_id": execution_context.task_id,
                    "run_id": execution_context.run_id,
                    "project_id": execution_context.project_id,
                    "objective": execution_context.objective,
                    "repair_attempt": attempt,
                },
            )

            if tool_names:
                workspace = self.workspace_manager.ensure(
                    execution_context.project_id,
                    execution_context.task_id,
                ).root
                tool_definitions = self.tools.resolve_many(tool_names)
                if not hasattr(provider, "generate_tool_turn"):
                    raise TypeError(
                        f"Provider '{type(provider).__name__}' does not support tool calling"
                    )

                loop_result = await self.tool_loop.run(
                    provider=provider,
                    contract=contract,
                    task=execution_context,
                    workspace=workspace,
                    tools=tool_definitions,
                    executor=self.tool_executor,
                )
                parsed = AgentModelOutput(
                    summary=loop_result.final_text or "Tool loop completed without final text.",
                    result={
                        "tool_calls": loop_result.tool_calls,
                        "tool_results": loop_result.tool_results,
                    },
                    artifact_markdown=(
                        "# Agent Tool Execution\n\n"
                        f"## Summary\n{loop_result.final_text}\n\n"
                        "## Tool trace\n"
                        f"{loop_result.tool_results}"
                    ),
                )
                provider_name = provider.name
                model_name = selection.route.model
                usage = {
                    **loop_result.usage,
                    "tool_calls": len(loop_result.tool_calls),
                    "repair_attempt": attempt,
                }
            else:
                response = await provider.generate(request, AgentModelOutput)
                parsed = response.parsed
                provider_name = response.provider
                model_name = response.model
                usage = {
                    **response.usage,
                    "repair_attempt": attempt,
                }

            evaluation = evaluate_execution(
                output=parsed,
                artifact_markdown=parsed.artifact_markdown,
            )

            if evaluation.passed:
                usage = self.model_router.enforce_usage(
                    route=selection.route,
                    usage=usage,
                    budget=ModelBudget(
                        max_input_tokens=settings.model_max_input_tokens,
                        max_output_tokens=settings.model_max_output_tokens,
                        max_cost=settings.model_max_cost,
                    ),
                )
                usage["repair_attempts_total"] = attempt - 1
                duration_ms = int((perf_counter() - started) * 1000)
                return AgentExecutionResult(
                    task_id=context.task_id,
                    agent_name=contract.name,
                    agent_version=contract.version,
                    provider=provider_name,
                    model=model_name,
                    status="COMPLETED",
                    output=parsed,
                    duration_ms=duration_ms,
                    usage=usage,
                    evaluation=evaluation.model_dump(),
                )

            plan = self.repair_planner.build(
                evaluation=evaluation,
                attempt=attempt,
                prior_context=repair_context,
            )
            if attempt > self.repair_policy.max_attempts:
                raise AgentEvaluationFailure(evaluation=evaluation, plan=plan)

            repair_context = {
                **repair_context,
                "repair_diagnosis": plan.diagnosis,
                "repair_context": plan.corrective_action,
                "failed_checks": plan.failed_checks,
            }

        raise RuntimeError("Repair loop exited without a terminal state")


_runtime: AgentRuntime | None = None


def get_agent_runtime() -> AgentRuntime:
    global _runtime
    if _runtime is None:
        _runtime = AgentRuntime()
    return _runtime
