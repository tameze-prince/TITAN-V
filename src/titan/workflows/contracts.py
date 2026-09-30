from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkflowTaskProfile:
    task_id: str
    risk_level: str = "R1"
    minimum_quality_tier: int = 1
    estimated_cost: float = 0.0
    expected_duration_ms: int = 0
    priority: int = 0
    provider_available: bool = True


@dataclass(frozen=True, slots=True)
class WorkflowInput:
    workflow_id: str
    project_id: str
    task_ids: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
    task_agents: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    agent_capacities: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    task_profiles: tuple[WorkflowTaskProfile, ...] = field(default_factory=tuple)
    max_project_cost: float = 0.0
    precompleted_task_ids: tuple[str, ...] = field(default_factory=tuple)
    approval_task_ids: tuple[str, ...] = field(default_factory=tuple)
    approval_quorums: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    approval_timeout_seconds: int = 86_400
    repair_max_attempts: int = 2
    recovery_attempt: int = 0
    recovery_root_workflow_id: str | None = None


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    workflow_id: str
    status: str
    completed_task_ids: tuple[str, ...] = field(default_factory=tuple)
    execution_waves: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    estimated_schedule_cost: float = 0.0
    estimated_makespan_ms: int = 0
    run_id: str | None = None
