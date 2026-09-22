from dataclasses import dataclass


RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4}


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str


class RuntimePolicy:
    def check(
        self,
        *,
        task_risk: str,
        agent_risk_ceiling: str,
        requested_capabilities: tuple[str, ...],
        requested_tools: tuple[str, ...],
        registered_capabilities: tuple[str, ...],
        allowed_tools: tuple[str, ...],
    ) -> PolicyDecision:
        self._validate_risk(task_risk)
        self._validate_risk(agent_risk_ceiling)

        if RISK_ORDER[task_risk] > RISK_ORDER[agent_risk_ceiling]:
            return PolicyDecision(False, "Task risk exceeds the agent risk ceiling")

        missing_capabilities = sorted(
            set(requested_capabilities).difference(registered_capabilities)
        )
        if missing_capabilities:
            return PolicyDecision(
                False,
                f"Unregistered capabilities requested: {', '.join(missing_capabilities)}",
            )

        unauthorized_tools = sorted(set(requested_tools).difference(allowed_tools))
        if unauthorized_tools:
            return PolicyDecision(
                False,
                f"Tools are not allowed by the agent contract: {', '.join(unauthorized_tools)}",
            )

        return PolicyDecision(True, "Policy checks passed")

    def check_tool(
        self,
        *,
        task_risk: str,
        agent_risk_ceiling: str,
        tool_risk: str,
        tool_name: str,
        allowed_tools: tuple[str, ...],
    ) -> PolicyDecision:
        self._validate_risk(task_risk)
        self._validate_risk(agent_risk_ceiling)
        self._validate_risk(tool_risk)

        if tool_name not in allowed_tools:
            return PolicyDecision(
                False,
                f"Tool '{tool_name}' is not allowed by the agent contract",
            )

        if RISK_ORDER[tool_risk] > RISK_ORDER[task_risk]:
            return PolicyDecision(
                False,
                f"Tool '{tool_name}' risk exceeds the task risk level",
            )

        if RISK_ORDER[tool_risk] > RISK_ORDER[agent_risk_ceiling]:
            return PolicyDecision(
                False,
                f"Tool '{tool_name}' risk exceeds the agent risk ceiling",
            )

        return PolicyDecision(True, "Tool policy checks passed")

    @staticmethod
    def _validate_risk(risk_level: str) -> None:
        if risk_level not in RISK_ORDER:
            raise ValueError(f"Unsupported risk level: {risk_level}")
