from dataclasses import dataclass
from typing import Any

from titan.runtime.providers import ModelProvider, ProviderRouter


@dataclass(frozen=True, slots=True)
class ModelRoute:
    name: str
    provider: str
    model: str
    quality_tier: int
    priority: int = 0
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ModelBudget:
    max_input_tokens: int = 64_000
    max_output_tokens: int = 16_000
    max_cost: float = 0.0


@dataclass(frozen=True, slots=True)
class ModelSelectionRequest:
    preferred_model: str
    minimum_quality_tier: int
    budget: ModelBudget


@dataclass(frozen=True, slots=True)
class ModelSelection:
    route: ModelRoute
    provider: ModelProvider


class BudgetExceeded(RuntimeError):
    pass


class ModelRouter:
    def __init__(self, provider_router: ProviderRouter) -> None:
        self.provider_router = provider_router
        self._routes: list[ModelRoute] = []

    def register(self, route: ModelRoute) -> None:
        if route.quality_tier < 0:
            raise ValueError("Model quality tier cannot be negative")
        if route.input_cost_per_1k < 0 or route.output_cost_per_1k < 0:
            raise ValueError("Model cost rates cannot be negative")
        if any(item.name == route.name for item in self._routes):
            raise ValueError(f"Model route '{route.name}' is already registered")
        self._routes.append(route)

    def select(self, request: ModelSelectionRequest) -> ModelSelection:
        candidates = [
            route
            for route in self._routes
            if route.enabled and route.quality_tier >= request.minimum_quality_tier
        ]
        if not candidates:
            raise LookupError("No model route satisfies the requested quality tier")

        preferred = [route for route in candidates if route.model == request.preferred_model]
        ordered = sorted(preferred or candidates, key=lambda route: route.priority, reverse=True)

        for route in ordered:
            try:
                provider = self.provider_router.resolve(route.provider)
            except KeyError:
                continue

            if self._fits_budget(route, request.budget):
                return ModelSelection(route=route, provider=provider)

        raise BudgetExceeded("No available model route satisfies the configured budget")

    @staticmethod
    def usage_tokens(usage: dict[str, Any]) -> tuple[int, int]:
        input_tokens = int(
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or 0
        )
        output_tokens = int(
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or 0
        )
        return input_tokens, output_tokens

    @staticmethod
    def estimate_cost(route: ModelRoute, usage: dict[str, Any]) -> float:
        input_tokens, output_tokens = ModelRouter.usage_tokens(usage)
        return (
            input_tokens / 1000 * route.input_cost_per_1k
            + output_tokens / 1000 * route.output_cost_per_1k
        )

    def enforce_usage(
        self,
        *,
        route: ModelRoute,
        usage: dict[str, Any],
        budget: ModelBudget,
    ) -> dict[str, Any]:
        input_tokens, output_tokens = self.usage_tokens(usage)
        cost = self.estimate_cost(route, usage)

        if input_tokens > budget.max_input_tokens:
            raise BudgetExceeded("Model input-token budget exceeded")
        if output_tokens > budget.max_output_tokens:
            raise BudgetExceeded("Model output-token budget exceeded")
        if budget.max_cost > 0 and cost > budget.max_cost:
            raise BudgetExceeded("Model cost budget exceeded")

        return {
            **usage,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": cost,
            "route": route.name,
            "quality_tier": route.quality_tier,
        }

    @staticmethod
    def _fits_budget(route: ModelRoute, budget: ModelBudget) -> bool:
        if budget.max_cost <= 0:
            return True
        estimated = (
            budget.max_input_tokens / 1000 * route.input_cost_per_1k
            + budget.max_output_tokens / 1000 * route.output_cost_per_1k
        )
        return estimated <= budget.max_cost
