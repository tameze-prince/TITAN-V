from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class FailureCategory(StrEnum):
    EVALUATION = "EVALUATION"
    PROVIDER = "PROVIDER"
    TOOL = "TOOL"
    BUDGET = "BUDGET"
    DEPENDENCY = "DEPENDENCY"
    UNKNOWN = "UNKNOWN"


class RecoveryStrategy(StrEnum):
    REPLAN_REASSIGN = "REPLAN_REASSIGN"
    REPLAN_SAME_AGENT = "REPLAN_SAME_AGENT"


@dataclass(frozen=True, slots=True)
class RecoveryObservation:
    category: FailureCategory
    strategy: RecoveryStrategy
    outcome: str
    actual_cost: float = 0.0
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class RecoveryStrategySelection:
    category: FailureCategory
    strategy: RecoveryStrategy
    reason: str
    score: float


def classify_failure(error_message: str) -> FailureCategory:
    message = error_message.lower()

    if any(token in message for token in ("budget", "token", "cost")):
        return FailureCategory.BUDGET
    if any(token in message for token in ("provider", "model", "api key", "rate limit")):
        return FailureCategory.PROVIDER
    if any(token in message for token in ("tool", "sandbox", "workspace", "permission")):
        return FailureCategory.TOOL
    if any(token in message for token in ("dependency", "blocked", "cycle")):
        return FailureCategory.DEPENDENCY
    if any(token in message for token in ("evaluation", "quality", "assertion")):
        return FailureCategory.EVALUATION
    return FailureCategory.UNKNOWN


class RecoveryStrategySelector:
    """Deterministically learn a bounded recovery strategy from durable outcomes."""

    _DEFAULT_SCORES = {
        RecoveryStrategy.REPLAN_REASSIGN: 0.50,
        RecoveryStrategy.REPLAN_SAME_AGENT: 0.45,
    }

    def select(
        self,
        *,
        category: FailureCategory,
        observations: Iterable[RecoveryObservation],
    ) -> RecoveryStrategySelection:
        relevant = [
            observation
            for observation in observations
            if observation.category == category
        ]

        if not relevant:
            return RecoveryStrategySelection(
                category=category,
                strategy=RecoveryStrategy.REPLAN_REASSIGN,
                reason="No historical recovery evidence exists for this failure category",
                score=self._DEFAULT_SCORES[RecoveryStrategy.REPLAN_REASSIGN],
            )

        scores = dict(self._DEFAULT_SCORES)
        for strategy in RecoveryStrategy:
            matching = [
                item
                for item in relevant
                if item.strategy == strategy
            ]
            if not matching:
                continue

            resolved = sum(item.outcome == "RESOLVED" for item in matching)
            repeated = sum(item.outcome == "REPEATED_FAILURE" for item in matching)
            escalated = sum(item.outcome == "ESCALATED" for item in matching)
            failed_to_start = sum(item.outcome == "FAILED_TO_START" for item in matching)
            total = len(matching)

            # Laplace smoothing prevents one early success/failure from dominating.
            resolved_rate = (resolved + 1) / (total + 2)
            failure_penalty = (
                repeated
                + (0.5 * failed_to_start)
                + (0.25 * escalated)
            ) / (total + 2)

            observed_costs = [item.actual_cost for item in matching if item.actual_cost > 0]
            observed_durations = [
                item.duration_ms for item in matching if item.duration_ms > 0
            ]
            max_cost = max(
                (item.actual_cost for item in relevant if item.actual_cost > 0),
                default=0.0,
            )
            max_duration = max(
                (item.duration_ms for item in relevant if item.duration_ms > 0),
                default=0,
            )
            avg_cost = sum(observed_costs) / len(observed_costs) if observed_costs else 0.0
            avg_duration = (
                sum(observed_durations) / len(observed_durations)
                if observed_durations
                else 0.0
            )
            cost_penalty = 0.10 * (avg_cost / max_cost) if max_cost else 0.0
            duration_penalty = (
                0.05 * (avg_duration / max_duration)
                if max_duration
                else 0.0
            )
            scores[strategy] = (
                resolved_rate
                - failure_penalty
                - cost_penalty
                - duration_penalty
            )

        ordered = sorted(
            RecoveryStrategy,
            key=lambda strategy: (
                scores[strategy],
                -list(RecoveryStrategy).index(strategy),
            ),
            reverse=True,
        )
        strategy = ordered[0]

        return RecoveryStrategySelection(
            category=category,
            strategy=strategy,
            reason=(
                f"Selected {strategy.value} from {len(relevant)} historical "
                f"{category.value} recovery observations"
            ),
            score=round(scores[strategy], 6),
        )


def observations_from_events(events: Iterable[object]) -> tuple[RecoveryObservation, ...]:
    outcome_map = {
        "RecoveryResolved": "RESOLVED",
        "RecoveryRepeatedFailure": "REPEATED_FAILURE",
        "RecoveryEscalated": "ESCALATED",
        "RecoveryFailed": "FAILED_TO_START",
    }
    observations: list[RecoveryObservation] = []

    for event in events:
        outcome = outcome_map.get(getattr(event, "type", ""))
        if outcome is None:
            continue
        payload = getattr(event, "payload", {}) or {}
        raw_category = payload.get("failure_category")
        raw_strategy = payload.get("strategy")
        try:
            category = FailureCategory(raw_category)
            strategy = RecoveryStrategy(raw_strategy)
        except ValueError:
            continue
        observations.append(
            RecoveryObservation(
                category=category,
                strategy=strategy,
                outcome=outcome,
                actual_cost=float(payload.get("actual_cost") or 0.0),
                duration_ms=int(payload.get("duration_ms") or 0),
            )
        )

    return tuple(observations)
