from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class WorkflowInput:
    workflow_id: UUID
    project_id: UUID
    task_ids: tuple[UUID, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    workflow_id: UUID
    status: str
    completed_task_ids: tuple[UUID, ...] = field(default_factory=tuple)
    run_id: UUID | None = None
