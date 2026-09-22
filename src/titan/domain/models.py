from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class Project:
    name: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Task:
    project_id: UUID
    objective: str
    id: UUID = field(default_factory=uuid4)
    status: str = "READY"


@dataclass(slots=True)
class Agent:
    name: str
    role: str
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Artifact:
    project_id: UUID
    name: str
    media_type: str
    id: UUID = field(default_factory=uuid4)


@dataclass(slots=True)
class Workflow:
    project_id: UUID
    name: str
    id: UUID = field(default_factory=uuid4)
    status: str = "CREATED"
