import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from titan.persistence.base import Base


task_dependencies = Table(
    "task_dependencies",
    Base.metadata,
    Column(
        "task_id",
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "depends_on_task_id",
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ProjectModel(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "autonomy_level BETWEEN 0 AND 5",
            name="autonomy_level_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    current_phase: Mapped[str] = mapped_column(
        String(64), nullable=False, default="DISCOVERY", server_default="DISCOVERY"
    )
    autonomy_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tasks: Mapped[list["TaskModel"]] = relationship(
        back_populates="project", passive_deletes=True
    )
    workflows: Mapped[list["WorkflowModel"]] = relationship(
        back_populates="project", passive_deletes=True
    )
    artifacts: Mapped[list["ArtifactModel"]] = relationship(
        back_populates="project", passive_deletes=True
    )
    events: Mapped[list["EventModel"]] = relationship(
        back_populates="project", passive_deletes=True
    )


class AgentModel(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0", server_default="1.0.0"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    tasks: Mapped[list["TaskModel"]] = relationship(back_populates="owner_agent")


class WorkflowModel(Base):
    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="GENERIC", server_default="GENERIC"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CREATED", server_default="CREATED"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    temporal_workflow_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    temporal_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[ProjectModel] = relationship(back_populates="workflows")
    tasks: Mapped[list["TaskModel"]] = relationship(back_populates="workflow")
    runs: Mapped[list["RunModel"]] = relationship(back_populates="workflow")


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "risk_level IN ('R0', 'R1', 'R2', 'R3', 'R4')",
            name="risk_level_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True
    )
    owner_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING", server_default="PENDING"
    )
    risk_level: Mapped[str] = mapped_column(
        String(8), nullable=False, default="R1", server_default="R1"
    )
    approval_requirement: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NONE", server_default="NONE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    project: Mapped[ProjectModel] = relationship(back_populates="tasks")
    workflow: Mapped[WorkflowModel | None] = relationship(back_populates="tasks")
    owner_agent: Mapped[AgentModel | None] = relationship(back_populates="tasks")
    runs: Mapped[list["RunModel"]] = relationship(back_populates="task")


class RunModel(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    temporal_workflow_id: Mapped[str] = mapped_column(String(255), nullable=False)
    temporal_run_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="RUNNING", server_default="RUNNING"
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    workflow: Mapped[WorkflowModel] = relationship(back_populates="runs")
    task: Mapped[TaskModel | None] = relationship(back_populates="runs")


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT", server_default="DRAFT"
    )
    media_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="text/markdown",
        server_default="text/markdown",
    )
    content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[ProjectModel] = relationship(back_populates="artifacts")


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[ProjectModel | None] = relationship(back_populates="events")
