from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkflowInput:
    workflow_id: str
    project_id: str
    task_ids: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[tuple[str, tuple[str, ...]], ...] = field(default_factory=tuple)
    task_agents: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    agent_capacities: tuple[tuple[str, int], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    workflow_id: str
    status: str
    completed_task_ids: tuple[str, ...] = field(default_factory=tuple)
    execution_waves: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    run_id: str | None = None
