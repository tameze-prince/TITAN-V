from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.database import get_session
from titan.persistence.models import (
    AgentModel,
    ArtifactModel,
    EventModel,
    GovernanceDecisionModel,
    ProjectModel,
    ProjectStateModel,
    TaskGraphModel,
    TaskModel,
    WorkflowModel,
)
from titan.runtime.explainability import build_project_explainability_trace
from titan.runtime.event_stream import build_event_stream_response
from titan.runtime.governance import task_requires_human_approval
from titan.runtime.operator_auth import OperatorIdentity, require_operator
from titan.runtime.recovery_metrics import collect_recovery_metrics


router = APIRouter(
    prefix="/api/v1/control-plane",
    tags=["control-plane"],
    dependencies=[Depends(require_operator)],
)


@router.get("/projects/{project_id}/events/stream")
async def stream_project_events(
    project_id: UUID,
    cursor: str | None = Query(default=None),
    operator: OperatorIdentity = Depends(require_operator),
):
    return await build_event_stream_response(
        project_id,
        cursor=cursor,
        operator=operator,
    )


class StatusCounts(BaseModel):
    total: int
    by_status: dict[str, int]


class AgentSummary(BaseModel):
    id: UUID
    name: str
    role: str
    version: str
    status: str


class ArtifactSummary(BaseModel):
    id: UUID
    type: str
    title: str
    version: int
    status: str
    media_type: str
    content_ref: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GovernanceSummary(BaseModel):
    id: UUID
    workflow_id: UUID | None
    task_id: UUID | None
    domain: str
    action: str
    allowed: bool
    requires_human: bool
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EventSummary(BaseModel):
    id: UUID
    type: str
    actor_type: str
    aggregate_type: str
    aggregate_id: UUID | None
    occurred_at: datetime
    payload: dict

    model_config = {"from_attributes": True}


class TaskApprovalAction(BaseModel):
    task_id: UUID
    workflow_id: UUID
    title: str
    objective: str
    risk_level: str
    status: str
    action: str
    reason: str


class RecoveryAction(BaseModel):
    workflow_id: UUID
    workflow_name: str
    workflow_type: str
    workflow_status: str
    action: str
    reason: str
    current_attempt: int | None = None
    failure_category: str | None = None


class TaskGraphSummary(BaseModel):
    id: UUID
    name: str
    version: int
    status: str
    objective: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectSummary(BaseModel):
    id: UUID
    name: str
    objective: str | None
    status: str
    current_phase: str
    autonomy_level: int
    updated_at: datetime
    task_counts: StatusCounts
    workflow_counts: StatusCounts


class ProjectSnapshot(BaseModel):
    id: UUID
    name: str
    objective: str | None
    status: str
    current_phase: str
    autonomy_level: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectStateSnapshot(BaseModel):
    project_id: UUID
    status: str
    phase: str
    version: int
    state_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectOverviewResponse(BaseModel):
    project: ProjectSnapshot
    state: ProjectStateSnapshot | None
    task_counts: StatusCounts
    workflow_counts: StatusCounts
    agents: list[AgentSummary]
    artifacts: list[ArtifactSummary]
    governance_decisions: list[GovernanceSummary]
    task_approval_actions: list[TaskApprovalAction]
    recovery_actions: list[RecoveryAction]
    pending_human_decisions: int
    pending_task_approvals: int
    recent_events: list[EventSummary]
    explainability: list[dict]
    recovery: dict
    latest_task_graph: TaskGraphSummary | None


class ControlPlaneOverviewResponse(BaseModel):
    projects: StatusCounts
    tasks: StatusCounts
    workflows: StatusCounts
    agents: StatusCounts
    artifacts: int
    pending_human_decisions: int


async def _status_counts(
    session: AsyncSession,
    model: type,
    *,
    project_id: UUID | None = None,
) -> StatusCounts:
    query = select(model.status, func.count()).group_by(model.status)
    if project_id is not None:
        query = query.where(model.project_id == project_id)

    rows = await session.execute(query)
    by_status = {str(status): int(count) for status, count in rows}
    return StatusCounts(total=sum(by_status.values()), by_status=by_status)


async def _require_project(
    session: AsyncSession,
    project_id: UUID,
) -> ProjectModel:
    project = await session.scalar(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


class OperatorIdentityResponse(BaseModel):
    subject: str
    role: str
    permissions: list[str]


@router.get("/me", response_model=OperatorIdentityResponse)
async def get_operator_identity(
    operator: OperatorIdentity = Depends(require_operator),
) -> OperatorIdentityResponse:
    from titan.runtime.operator_auth import ROLE_PERMISSIONS

    return OperatorIdentityResponse(
        subject=operator.subject,
        role=operator.role,
        permissions=sorted(ROLE_PERMISSIONS.get(operator.role, frozenset())),
    )


@router.get("/overview", response_model=ControlPlaneOverviewResponse)
async def get_control_plane_overview(
    session: AsyncSession = Depends(get_session),
) -> ControlPlaneOverviewResponse:
    projects = await _status_counts(session, ProjectModel)
    tasks = await _status_counts(session, TaskModel)
    workflows = await _status_counts(session, WorkflowModel)
    agents = await _status_counts(session, AgentModel)

    artifacts = int(
        await session.scalar(select(func.count()).select_from(ArtifactModel)) or 0
    )
    pending_human_decisions = int(
        await session.scalar(
            select(func.count())
            .select_from(GovernanceDecisionModel)
            .where(GovernanceDecisionModel.requires_human.is_(True))
        )
        or 0
    )

    return ControlPlaneOverviewResponse(
        projects=projects,
        tasks=tasks,
        workflows=workflows,
        agents=agents,
        artifacts=artifacts,
        pending_human_decisions=pending_human_decisions,
    )


@router.get("/projects", response_model=list[ProjectSummary])
async def list_control_plane_projects(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectSummary]:
    projects = list(
        await session.scalars(
            select(ProjectModel)
            .order_by(ProjectModel.updated_at.desc())
            .limit(limit)
        )
    )

    summaries: list[ProjectSummary] = []
    for project in projects:
        summaries.append(
            ProjectSummary(
                id=project.id,
                name=project.name,
                objective=project.objective,
                status=project.status,
                current_phase=project.current_phase,
                autonomy_level=project.autonomy_level,
                updated_at=project.updated_at,
                task_counts=await _status_counts(
                    session, TaskModel, project_id=project.id
                ),
                workflow_counts=await _status_counts(
                    session, WorkflowModel, project_id=project.id
                ),
            )
        )
    return summaries


@router.get(
    "/projects/{project_id}",
    response_model=ProjectOverviewResponse,
)
async def get_project_control_plane(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ProjectOverviewResponse:
    project = await _require_project(session, project_id)

    state = await session.scalar(
        select(ProjectStateModel).where(ProjectStateModel.project_id == project_id)
    )

    task_counts = await _status_counts(session, TaskModel, project_id=project_id)
    workflow_counts = await _status_counts(
        session, WorkflowModel, project_id=project_id
    )

    agent_ids = (
        select(TaskModel.owner_agent_id)
        .where(
            TaskModel.project_id == project_id,
            TaskModel.owner_agent_id.is_not(None),
        )
        .distinct()
        .subquery()
    )
    agents = list(
        await session.scalars(
            select(AgentModel)
            .where(AgentModel.id.in_(select(agent_ids.c.owner_agent_id)))
            .order_by(AgentModel.name.asc())
        )
    )

    artifacts = list(
        await session.scalars(
            select(ArtifactModel)
            .where(ArtifactModel.project_id == project_id)
            .order_by(ArtifactModel.created_at.desc())
            .limit(25)
        )
    )

    governance_decisions = list(
        await session.scalars(
            select(GovernanceDecisionModel)
            .where(GovernanceDecisionModel.project_id == project_id)
            .order_by(GovernanceDecisionModel.created_at.desc())
            .limit(25)
        )
    )

    recovery_workflows = list(
        await session.scalars(
            select(WorkflowModel)
            .where(
                WorkflowModel.project_id == project_id,
                WorkflowModel.workflow_type == "RECOVERY",
            )
            .order_by(WorkflowModel.created_at.desc())
            .limit(50)
        )
    )

    recovery_events = list(
        await session.scalars(
            select(EventModel)
            .where(
                EventModel.project_id == project_id,
                EventModel.aggregate_type == "WORKFLOW",
                EventModel.type.in_(
                    ("RecoveryEscalated", "RecoveryApproved", "RecoveryRejected")
                ),
            )
            .order_by(EventModel.occurred_at.desc())
            .limit(200)
        )
    )

    latest_recovery_decision: dict[UUID, EventModel] = {}
    for event in recovery_events:
        if (
            event.aggregate_id is not None
            and event.aggregate_id not in latest_recovery_decision
        ):
            latest_recovery_decision[event.aggregate_id] = event

    recovery_actions: list[RecoveryAction] = []
    for event_workflow_id, event in latest_recovery_decision.items():
        if event.type != "RecoveryEscalated":
            continue

        source_workflow = await session.scalar(
            select(WorkflowModel).where(
                WorkflowModel.id == event_workflow_id,
                WorkflowModel.project_id == project_id,
            )
        )
        if source_workflow is None or source_workflow.status != "FAILED":
            continue

        payload = event.payload or {}
        recovery_actions.append(
            RecoveryAction(
                workflow_id=source_workflow.id,
                workflow_name=source_workflow.name,
                workflow_type=source_workflow.workflow_type,
                workflow_status=source_workflow.status,
                action="APPROVE_OR_REJECT_RECOVERY",
                reason=str(
                    payload.get("reason") or "Recovery requires operator decision"
                ),
                current_attempt=int(payload.get("current_attempt", 0)),
                failure_category=(
                    str(payload.get("failure_category"))
                    if payload.get("failure_category") is not None
                    else None
                ),
            )
        )

    for recovery_workflow in recovery_workflows:
        if recovery_workflow.status in {"STARTING", "RUNNING"}:
            recovery_actions.append(
                RecoveryAction(
                    workflow_id=recovery_workflow.id,
                    workflow_name=recovery_workflow.name,
                    workflow_type=recovery_workflow.workflow_type,
                    workflow_status=recovery_workflow.status,
                    action="ROLLBACK_RECOVERY",
                    reason="Active recovery workflow can be rolled back by an operator",
                )
            )

    task_approval_tasks = list(
        await session.scalars(
            select(TaskModel)
            .where(
                TaskModel.project_id == project_id,
                TaskModel.status == "WAITING_APPROVAL",
            )
            .order_by(TaskModel.updated_at.desc())
            .limit(50)
        )
    )
    task_approval_actions = [
        TaskApprovalAction(
            task_id=task.id,
            workflow_id=task.workflow_id,
            title=task.title,
            objective=task.objective,
            risk_level=task.risk_level,
            status=task.status,
            action="APPROVE_OR_REJECT_TASK",
            reason="Task is waiting for an operator approval before execution",
        )
        for task in task_approval_tasks
        if task.workflow_id is not None
        and task_requires_human_approval(
            risk_level=task.risk_level,
            approval_requirement=task.approval_requirement,
        )
    ]

    pending_human_decisions = int(
        await session.scalar(
            select(func.count())
            .select_from(GovernanceDecisionModel)
            .where(
                GovernanceDecisionModel.project_id == project_id,
                GovernanceDecisionModel.requires_human.is_(True),
            )
        )
        or 0
    )

    pending_task_approvals = int(
        await session.scalar(
            select(func.count())
            .select_from(TaskModel)
            .where(
                TaskModel.project_id == project_id,
                TaskModel.approval_requirement != "NONE",
                TaskModel.status == "WAITING_APPROVAL",
            )
        )
        or 0
    )

    recent_events = list(
        await session.scalars(
            select(EventModel)
            .where(EventModel.project_id == project_id)
            .order_by(EventModel.occurred_at.desc())
            .limit(50)
        )
    )

    trace = await build_project_explainability_trace(
        session,
        project_id=project_id,
        limit=50,
    )
    explainability = [
        {
            "occurred_at": item.occurred_at,
            "stage": item.stage,
            "event_type": item.event_type,
            "actor_type": item.actor_type,
            "aggregate_type": item.aggregate_type,
            "aggregate_id": item.aggregate_id,
            "summary": item.summary,
            "details": item.details,
        }
        for item in trace
    ]

    recovery = await collect_recovery_metrics(
        session,
        project_id=project_id,
    )

    latest_task_graph = await session.scalar(
        select(TaskGraphModel)
        .where(TaskGraphModel.project_id == project_id)
        .order_by(TaskGraphModel.version.desc())
        .limit(1)
    )

    return ProjectOverviewResponse(
        project=ProjectSnapshot.model_validate(project),
        state=ProjectStateSnapshot.model_validate(state) if state is not None else None,
        task_counts=task_counts,
        workflow_counts=workflow_counts,
        agents=[
            AgentSummary(
                id=agent.id,
                name=agent.name,
                role=agent.role,
                version=agent.version,
                status=agent.status,
            )
            for agent in agents
        ],
        artifacts=artifacts,
        governance_decisions=governance_decisions,
        task_approval_actions=task_approval_actions,
        recovery_actions=recovery_actions,
        pending_human_decisions=pending_human_decisions,
        pending_task_approvals=pending_task_approvals,
        recent_events=recent_events,
        explainability=explainability,
        recovery={
            "started": recovery.started,
            "resolved": recovery.resolved,
            "repeated_failures": recovery.repeated_failures,
            "escalated": recovery.escalated,
            "failed_to_start": recovery.failed_to_start,
            "terminal_attempts": recovery.terminal_attempts,
            "resolved_ratio": recovery.resolved_ratio,
            "latest_outcome": recovery.latest_outcome,
            "strategy_counts": recovery.strategy_counts,
        },
        latest_task_graph=latest_task_graph,
    )
