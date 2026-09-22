import pytest

from titan.runtime.model_router import (
    BudgetExceeded,
    ModelBudget,
    ModelRoute,
    ModelRouter,
    ModelSelectionRequest,
)
from titan.runtime.providers import LocalStructuredProvider, ProviderRouter


def build_router() -> ModelRouter:
    providers = ProviderRouter({"local": LocalStructuredProvider()})
    router = ModelRouter(providers)
    router.register(
        ModelRoute(
            name="local",
            provider="local",
            model="local",
            quality_tier=1,
            priority=10,
        )
    )
    return router


def test_model_router_selects_preferred_route() -> None:
    router = build_router()

    selection = router.select(
        ModelSelectionRequest(
            preferred_model="local",
            minimum_quality_tier=1,
            budget=ModelBudget(),
        )
    )

    assert selection.route.name == "local"
    assert selection.provider.name == "local"


def test_model_router_enforces_token_budget() -> None:
    router = build_router()

    with pytest.raises(BudgetExceeded, match="input-token"):
        router.enforce_usage(
            route=ModelRoute(
                name="local",
                provider="local",
                model="local",
                quality_tier=1,
            ),
            usage={"input_tokens": 1001, "output_tokens": 1},
            budget=ModelBudget(max_input_tokens=1000),
        )


def test_model_router_calculates_cost_from_configured_rates() -> None:
    router = build_router()

    cost = router.estimate_cost(
        ModelRoute(
            name="priced",
            provider="local",
            model="local",
            quality_tier=1,
            input_cost_per_1k=0.5,
            output_cost_per_1k=1.0,
        ),
        {"input_tokens": 2000, "output_tokens": 1000},
    )

    assert cost == pytest.approx(2.0)


def test_model_router_can_route_custom_provider_model() -> None:
    router = ModelRouter(
        ProviderRouter({"local": LocalStructuredProvider()})
    )

    selection = router.select(
        ModelSelectionRequest(
            preferred_model="local",
            minimum_quality_tier=1,
            budget=ModelBudget(),
        )
    )

    assert selection.route.provider == "local"
