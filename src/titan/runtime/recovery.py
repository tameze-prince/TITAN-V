from dataclasses import dataclass

RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


@dataclass(frozen=True, slots=True)
class RecoveryAssessment:
    action: str
    reason: str
    next_attempt: int
    max_attempts: int


@dataclass(frozen=True, slots=True)
class RecoveryPolicy:
    enabled: bool = False
    max_attempts: int = 2
    min_autonomy_level: int = 3
    max_auto_risk_level: str = "R1"

    def assess(
        self,
        *,
        autonomy_level: int,
        current_attempt: int,
        failed_risk_levels: tuple[str, ...],
        approval_required: bool,
    ) -> RecoveryAssessment:
        if self.max_attempts < 1:
            raise ValueError("Recovery max_attempts must be at least 1")
        if self.min_autonomy_level < 0:
            raise ValueError("Recovery minimum autonomy level cannot be negative")
        if self.max_auto_risk_level not in RISK_ORDER:
            raise ValueError(
                f"Unsupported automatic recovery risk ceiling: {self.max_auto_risk_level}"
            )

        if current_attempt >= self.max_attempts:
            return RecoveryAssessment(
                action="ESCALATE",
                reason="Automatic recovery attempt budget exhausted",
                next_attempt=current_attempt,
                max_attempts=self.max_attempts,
            )

        if not self.enabled:
            return RecoveryAssessment(
                action="ESCALATE",
                reason="Automatic recovery is disabled by deployment policy",
                next_attempt=current_attempt,
                max_attempts=self.max_attempts,
            )

        if autonomy_level < self.min_autonomy_level:
            return RecoveryAssessment(
                action="ESCALATE",
                reason=(
                    f"Project autonomy level {autonomy_level} is below the "
                    f"automatic recovery threshold {self.min_autonomy_level}"
                ),
                next_attempt=current_attempt,
                max_attempts=self.max_attempts,
            )

        if approval_required:
            return RecoveryAssessment(
                action="ESCALATE",
                reason="One or more failed tasks require human approval",
                next_attempt=current_attempt,
                max_attempts=self.max_attempts,
            )

        if any(
            risk not in RISK_ORDER
            or RISK_ORDER[risk] > RISK_ORDER[self.max_auto_risk_level]
            for risk in failed_risk_levels
        ):
            return RecoveryAssessment(
                action="ESCALATE",
                reason=(
                    "Failed work exceeds the configured automatic recovery "
                    f"risk ceiling of {self.max_auto_risk_level}"
                ),
                next_attempt=current_attempt,
                max_attempts=self.max_attempts,
            )

        return RecoveryAssessment(
            action="AUTO_RECOVER",
            reason="Failure is eligible for bounded automatic recovery",
            next_attempt=current_attempt + 1,
            max_attempts=self.max_attempts,
        )
