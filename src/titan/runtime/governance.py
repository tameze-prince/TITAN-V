from dataclasses import dataclass
from enum import StrEnum

from titan.runtime.model_router import ModelBudget, ModelSelection
from titan.runtime.policies import PolicyDecision
from titan.runtime.recovery import RecoveryAssessment


class GovernanceAction(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


@dataclass(frozen=True, slots=True)
class GovernanceCheck:
    policy: str
    action: GovernanceAction
    reason: str


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    action: GovernanceAction
    allowed: bool
    requires_human: bool
    reason: str
    checks: tuple[GovernanceCheck, ...] = ()


class GovernanceEngine:
    """Compose execution, model, and recovery policies into one decision."""

    @staticmethod
    def from_policy_decision(
        *,
        policy: str,
        decision: PolicyDecision,
    ) -> GovernanceCheck:
        return GovernanceCheck(
            policy=policy,
            action=(
                GovernanceAction.ALLOW
                if decision.allowed
                else GovernanceAction.DENY
            ),
            reason=decision.reason,
        )

    @staticmethod
    def check_model(
        *,
        selection: ModelSelection,
        minimum_quality_tier: int,
        budget: ModelBudget,
    ) -> GovernanceCheck:
        route = selection.route
        if route.quality_tier < minimum_quality_tier:
            return GovernanceCheck(
                policy="model",
                action=GovernanceAction.DENY,
                reason=(
                    f"Selected route quality tier {route.quality_tier} is below "
                    f"required tier {minimum_quality_tier}"
                ),
            )

        if budget.max_cost > 0:
            estimated_cost = (
                budget.max_input_tokens / 1000 * route.input_cost_per_1k
                + budget.max_output_tokens / 1000 * route.output_cost_per_1k
            )
            if estimated_cost > budget.max_cost:
                return GovernanceCheck(
                    policy="model-budget",
                    action=GovernanceAction.DENY,
                    reason=(
                        f"Estimated maximum model cost {estimated_cost:.6f} "
                        f"exceeds configured budget {budget.max_cost:.6f}"
                    ),
                )

        return GovernanceCheck(
            policy="model",
            action=GovernanceAction.ALLOW,
            reason="Model route satisfies quality and budget governance",
        )

    @staticmethod
    def check_recovery(
        assessment: RecoveryAssessment,
        *,
        human_approved: bool = False,
    ) -> GovernanceCheck:
        if assessment.action == "AUTO_RECOVER":
            return GovernanceCheck(
                policy="recovery",
                action=GovernanceAction.ALLOW,
                reason=assessment.reason,
            )

        if human_approved:
            return GovernanceCheck(
                policy="recovery",
                action=GovernanceAction.ALLOW,
                reason="Human approval authorizes the escalated recovery decision",
            )

        return GovernanceCheck(
            policy="recovery",
            action=GovernanceAction.APPROVAL_REQUIRED,
            reason=assessment.reason,
        )

    @staticmethod
    def decide(checks: tuple[GovernanceCheck, ...]) -> GovernanceDecision:
        if any(check.action is GovernanceAction.DENY for check in checks):
            reasons = "; ".join(
                check.reason
                for check in checks
                if check.action is GovernanceAction.DENY
            )
            return GovernanceDecision(
                action=GovernanceAction.DENY,
                allowed=False,
                requires_human=False,
                reason=reasons or "A governance policy denied the operation",
                checks=checks,
            )

        if any(
            check.action is GovernanceAction.APPROVAL_REQUIRED
            for check in checks
        ):
            reasons = "; ".join(
                check.reason
                for check in checks
                if check.action is GovernanceAction.APPROVAL_REQUIRED
            )
            return GovernanceDecision(
                action=GovernanceAction.APPROVAL_REQUIRED,
                allowed=False,
                requires_human=True,
                reason=reasons or "Human approval is required",
                checks=checks,
            )

        return GovernanceDecision(
            action=GovernanceAction.ALLOW,
            allowed=True,
            requires_human=False,
            reason="All governance policies passed",
            checks=checks,
        )

    @classmethod
    def decide_runtime(
        cls,
        *,
        runtime_policy: PolicyDecision,
        selection: ModelSelection,
        minimum_quality_tier: int,
        budget: ModelBudget,
    ) -> GovernanceDecision:
        return cls.decide(
            (
                cls.from_policy_decision(policy="runtime", decision=runtime_policy),
                cls.check_model(
                    selection=selection,
                    minimum_quality_tier=minimum_quality_tier,
                    budget=budget,
                ),
            )
        )
