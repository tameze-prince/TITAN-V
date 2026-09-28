from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from titan import __version__
from titan.api.control_plane import router as control_plane_router
from titan.config import settings
from titan.integrations.temporal.client import get_temporal_client
from titan.persistence.database import close_database, get_session
from titan.persistence.models import (
    AgentModel,
    EventModel,
    GovernanceDecisionModel,
    IntentRecordModel,
    ProjectModel,
    PolicyVersionModel,
    ProjectStateModel,
    TaskGraphModel,
    TaskModel,
    WorkflowModel,
    task_dependencies,
)
from titan.runtime.explainability import build_project_explainability_trace
from titan.runtime.intent import IntentCompiler, IntentRepresentation
from titan.runtime.memory import MemoryStore
from titan.runtime.policy_store import PolicyDefinition, PolicyVersionStore
from titan.runtime.model_router import BudgetExceeded, ModelBudget, ModelSelectionRequest
from titan.runtime.operator_auth import OperatorIdentity, require_operator
from titan.runtime.planner import CapabilityResolutionError, TaskGraphPlanner
from titan.runtime.scheduler import DependencyAwareScheduler, TaskScheduleError, TaskSchedulingProfile
from titan.runtime.planning_service import persist_task_graph
from titan.runtime.replanning_service import replan_failed_workflow
from titan.runtime.recovery_service import start_recovery_workflow
from titan.runtime.recovery_strategy import (
    FailureCategory,
    RecoveryStrategy,
    RecoveryStrategySelector,
    classify_failure,
    observations_from_events,
)
from titan.runtime.recovery_metrics import collect_recovery_metrics
from titan.runtime.service import get_agent_runtime
from titan.workflows.contracts import WorkflowInput, WorkflowTaskProfile
from titan.workflows.runtime import TitanWorkflow




class ExplainabilityStepResponse(BaseModel):
    occurred_at: datetime
    stage: str
    event_type: str
    actor_type: str
    aggregate_type: str
    aggregate_id: UUID | None
    summary: str
    details: dict


class PolicyCreateRequest(BaseModel):
    policy_name: str = Field(min_length=1, max_length=120)
    scope_type: str = Field(default="GLOBAL", min_length=1, max_length=32)
    scope_id: UUID | None = None
    definition: PolicyDefinition = Field(default_factory=PolicyDefinition)
    activate: bool = True
    created_by: str = Field(default="SYSTEM", min_length=1, max_length=120)


class PolicyVersionResponse(BaseModel):
    id: UUID
    scope_type: str
    scope_id: UUID | None
    policy_name: str
    version: int
    status: str
    definition_json: dict
    created_by: str

    model_config = {"from_attributes": True}


class GovernanceDecisionResponse(BaseModel):
    id: UUID
    project_id: UUID | None
    workflow_id: UUID | None
    task_id: UUID | None
    policy_version_id: UUID | None
    domain: str
    action: str
    allowed: bool
    requires_human: bool
    reason: str
    checks_json: list
    context_json: dict

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    objective: str | None = Field(default=None, max_length=10_000)


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    objective: str | None
    status: str
    current_phase: str
    autonomy_level: int

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    objective: str = Field(min_length=1, max_length=10_000)
    risk_level: str = Field(default="R1", pattern=r"^R[0-4]$")


class TaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    workflow_id: UUID | None
    task_graph_id: UUID | None
    task_key: str | None
    title: str
    objective: str
    status: str
    risk_level: str
    position: int
    required_capabilities: list[str]

    model_config = {"from_attributes": True}


class TaskApprovalRequest(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=2_000)


class TaskApprovalResponse(BaseModel):
    project_id: UUID
    task_id: UUID
    workflow_id: UUID
    decision: str
    reason: str
    status: str


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    workflow_type: str = Field(default="GENERIC", min_length=1, max_length=64)
    task_ids: list[UUID] = Field(default_factory=list, max_length=100)
    task_graph_id: UUID | None = None

    @model_validator(mode="after")
    def validate_task_source(self):
        if bool(self.task_ids) == (self.task_graph_id is not None):
            raise ValueError("Provide exactly one of task_ids or task_graph_id")
        return self


class WorkflowResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    workflow_type: str
    status: str
    temporal_workflow_id: str | None
    temporal_run_id: str | None

    model_config = {"from_attributes": True}



class IntentCompileRequest(BaseModel):
    raw_intent: str = Field(min_length=1, max_length=20_000)
    user_context: dict = Field(default_factory=dict)
    project_context: dict = Field(default_factory=dict)


class IntentCompileResponse(BaseModel):
    id: UUID
    project_id: UUID
    raw_intent: str
    compiled: IntentRepresentation
    provider: str
    model: str
    status: str
    version: int

    model_config = {"from_attributes": True}


class PlanCreate(BaseModel):
    intent_record_id: UUID | None = None


class PlannedTaskResponse(BaseModel):
    id: UUID
    task_key: str
    title: str
    objective: str
    position: int
    dependencies: list[str]
    required_capabilities: list[str]
    agent_name: str
    risk_level: str
    status: str


class TaskGraphResponse(BaseModel):
    id: UUID
    project_id: UUID
    intent_record_id: UUID
    name: str
    version: int
    status: str
    objective: str
    tasks: list[PlannedTaskResponse]
    unknowns: list[str]
    constraints: list[str]
    risks: list[str]


class ProjectStateResponse(BaseModel):
    project_id: UUID
    status: str
    phase: str
    version: int
    state: dict

class AgentReassignmentResponse(BaseModel):
    task_id: UUID
    previous_agent: str | None
    new_agent: str
    reason: str


class ReplanResponse(BaseModel):
    task_graph_id: UUID
    project_id: UUID
    source_workflow_id: UUID
    version: int
    status: str
    failed_task_ids: list[UUID]
    impacted_task_ids: list[UUID]
    reassignments: list[AgentReassignmentResponse]




@app.post(
    "/api/v1/policies",
    status_code=status.HTTP_201_CREATED,
    response_model=PolicyVersionResponse,
)
async def create_policy_version(
    payload: PolicyCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> PolicyVersionModel:
    store = PolicyVersionStore()
    try:
        row = await store.create(
            session,
            policy_name=payload.policy_name,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            definition=payload.definition,
            created_by=payload.created_by,
            activate=payload.activate,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    session.add(
        EventModel(
            project_id=payload.scope_id if payload.scope_type.upper() == "PROJECT" else None,
            type="PolicyVersionCreated",
            actor_type="SYSTEM",
            aggregate_type="POLICY",
            aggregate_id=row.id,
            payload={
                "policy_name": row.policy_name,
                "scope_type": row.scope_type,
                "scope_id": str(row.scope_id) if row.scope_id else None,
                "version": row.version,
                "status": row.status,
                "created_by": row.created_by,
            },
        )
    )
    await session.commit()
    await session.refresh(row)
    return row


@app.get(
    "/api/v1/policies",
    response_model=list[PolicyVersionResponse],
)
async def list_policy_versions(
    policy_name: str | None = None,
    scope_type: str | None = None,
    scope_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[PolicyVersionModel]:
    return await PolicyVersionStore().list_versions(
        session,
        policy_name=policy_name,
        scope_type=scope_type,
        scope_id=scope_id,
    )


@app.get(
    "/api/v1/projects/{project_id}/governance/decisions",
    response_model=list[GovernanceDecisionResponse],
)
async def list_governance_decisions(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[GovernanceDecisionModel]:
    project = await session.scalar(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return list(
        await session.scalars(
            select(GovernanceDecisionModel)
            .where(GovernanceDecisionModel.project_id == project_id)
            .order_by(GovernanceDecisionModel.created_at.desc())
        )
    )



@app.get(
    "/api/v1/projects/{project_id}/explainability",
    response_model=list[ExplainabilityStepResponse],
)
async def get_project_explainability(
    project_id: UUID,
    workflow_id: UUID | None = None,
    limit: int = 500,
    session: AsyncSession = Depends(get_session),
) -> list[ExplainabilityStepResponse]:
    if limit < 1 or limit > 2_000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 2000",
        )

    project = await session.scalar(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    steps = await build_project_explainability_trace(
        session,
        project_id=project_id,
        workflow_id=workflow_id,
        limit=limit,
    )
    return [
        ExplainabilityStepResponse(
            occurred_at=step.occurred_at,
            stage=step.stage,
            event_type=step.event_type,
            actor_type=step.actor_type,
            aggregate_type=step.aggregate_type,
            aggregate_id=step.aggregate_id,
            summary=step.summary,
            details=step.details,
        )
        for step in steps
    ]


class RecoveryDecisionRequest(BaseModel):
    approved: bool
    strategy: RecoveryStrategy | None = None
    reason: str = Field(default="", max_length=2_000)


class RecoveryDecisionResponse(BaseModel):
    project_id: UUID
    workflow_id: UUID
    decision: str
    strategy: str | None
    replacement_workflow_id: UUID | None
    message: str


class RecoveryRollbackRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2_000)


class RecoveryRollbackResponse(BaseModel):
    project_id: UUID
    recovery_workflow_id: UUID
    source_workflow_id: UUID | None
    status: str
    reason: str


class RecoveryMetricsResponse(BaseModel):
    project_id: UUID
    started: int
    resolved: int
    repeated_failures: int
    escalated: int
    failed_to_start: int
    terminal_attempts: int
    resolved_ratio: float
    latest_outcome: str | None
    strategy_counts: dict[str, int]


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_database()


app = FastAPI(title="TITAN V.", version=__version__, lifespan=lifespan)
app.include_router(control_plane_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post(
    "/api/v1/projects",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectResponse,
)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> ProjectModel:
    project = ProjectModel(name=payload.name, objective=payload.objective)
    session.add(project)
    await session.flush()

    session.add(
        ProjectStateModel(
            project_id=project.id,
            status="ACTIVE",
            phase="DISCOVERY",
            version=1,
            state_json={
                "objective": project.objective,
                "task_graph_id": None,
                "intent_record_id": None,
            },
        )
    )
    session.add(
        EventModel(
            project_id=project.id,
            type="ProjectCreated",
            actor_type="SYSTEM",
            aggregate_type="PROJECT",
            aggregate_id=project.id,
            payload={"name": project.name},
        )
    )
    session.add(
        EventModel(
            project_id=project.id,
            type="ProjectStateInitialized",
            actor_type="SYSTEM",
            aggregate_type="PROJECT_STATE",
            aggregate_id=project.id,
            payload={"phase": "DISCOVERY", "status": "ACTIVE", "version": 1},
        )
    )

    await session.commit()
    await session.refresh(project)
    return project


@app.get("/api/v1/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ProjectModel:
    project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project



@app.post(
    "/api/v1/projects/{project_id}/intent",
    status_code=status.HTTP_201_CREATED,
    response_model=IntentCompileResponse,
)
async def compile_project_intent(
    project_id: UUID,
    payload: IntentCompileRequest,
    session: AsyncSession = Depends(get_session),
) -> IntentRecordModel:
    project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    runtime = get_agent_runtime()
    selection = runtime.model_router.select(
        ModelSelectionRequest(
            preferred_model=runtime.contracts.resolve("general-executor").model,
            minimum_quality_tier=1,
            budget=ModelBudget(
                max_input_tokens=settings.model_max_input_tokens,
                max_output_tokens=settings.model_max_output_tokens,
                max_cost=settings.model_max_cost,
            ),
        )
    )
    compiler = IntentCompiler(selection.provider, selection.route.model)
    try:
        result = await compiler.compile(
            raw_intent=payload.raw_intent,
            project_context=payload.project_context,
            user_context=payload.user_context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to compile project intent",
        ) from exc

    record = IntentRecordModel(
        project_id=project_id,
        raw_intent=payload.raw_intent,
        compiled=result.representation.model_dump(mode="json"),
        provider=result.provider,
        model=result.model,
        status="COMPILED",
    )
    session.add(record)
    await session.flush()

    if project.objective is None:
        project.objective = result.representation.desired_outcome or payload.raw_intent

    state = await session.scalar(
        select(ProjectStateModel).where(ProjectStateModel.project_id == project_id)
    )
    if state is None:
        state = ProjectStateModel(
            project_id=project_id,
            status="ACTIVE",
            phase="PLANNING",
            version=1,
        )
        session.add(state)
    else:
        state.status = "ACTIVE"
        state.phase = "PLANNING"
        state.version += 1
    state.state_json = {
        **state.state_json,
        "intent_record_id": str(record.id),
        "objective": project.objective,
        "unknowns": list(result.representation.unknowns),
        "constraints": list(result.representation.constraints),
        "risks": list(result.representation.risks),
    }
    project.current_phase = "PLANNING"

    memory_store = MemoryStore()
    await memory_store.remember(
        session,
        project_id=project_id,
        task_id=None,
        kind="INTENT",
        content=payload.raw_intent,
        importance=90,
        source_type="INTENT_COMPILER",
        source_id=record.id,
        metadata={
            "provider": result.provider,
            "model": result.model,
            "required_capabilities": result.representation.required_capabilities,
        },
    )

    session.add(
        EventModel(
            project_id=project_id,
            type="IntentCompiled",
            actor_type="SYSTEM",
            aggregate_type="PROJECT",
            aggregate_id=project_id,
            payload={
                "intent_record_id": str(record.id),
                "provider": result.provider,
                "model": result.model,
                "required_capabilities": result.representation.required_capabilities,
            },
        )
    )
    session.add(
        EventModel(
            project_id=project_id,
            type="ModelUsageRecorded",
            actor_type="SYSTEM",
            aggregate_type="PROJECT",
            aggregate_id=project_id,
            payload={
                "component": "intent-compiler",
                "intent_record_id": str(record.id),
                "provider": result.provider,
                "model": result.model,
                "usage": result.usage,
            },
        )
    )

    await session.commit()
    await session.refresh(record)
    return record

@app.post(
    "/api/v1/projects/{project_id}/plan",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskGraphResponse,
)
async def create_task_graph_plan(
    project_id: UUID,
    payload: PlanCreate,
    session: AsyncSession = Depends(get_session),
) -> TaskGraphResponse:
    project = await session.scalar(
        select(ProjectModel)
        .where(ProjectModel.id == project_id)
        .with_for_update()
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if payload.intent_record_id is not None:
        intent_record = await session.scalar(
            select(IntentRecordModel).where(
                IntentRecordModel.id == payload.intent_record_id,
                IntentRecordModel.project_id == project_id,
            )
        )
    else:
        intent_record = await session.scalar(
            select(IntentRecordModel)
            .where(IntentRecordModel.project_id == project_id)
            .order_by(IntentRecordModel.created_at.desc())
            .limit(1)
        )

    if intent_record is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A compiled project intent is required before planning",
        )

    latest_version = await session.scalar(
        select(TaskGraphModel.version)
        .where(TaskGraphModel.project_id == project_id)
        .order_by(TaskGraphModel.version.desc())
        .limit(1)
    )
    version = (latest_version or 0) + 1

    runtime = get_agent_runtime()
    intent = IntentRepresentation.model_validate(intent_record.compiled)
    planner = TaskGraphPlanner(runtime.capabilities, runtime.contracts.all())
    try:
        plan = planner.plan(intent, version=version)
    except CapabilityResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "The compiled intent requires capabilities that are not registered",
                "missing_capabilities": list(exc.missing),
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    graph, tasks = await persist_task_graph(
        session,
        project=project,
        intent_record=intent_record,
        intent=intent,
        plan=plan,
        contracts=runtime.contracts.all(),
    )
    await session.commit()

    node_by_key = {node.key: node for node in plan.nodes}
    response_tasks = []
    for task in sorted(tasks, key=lambda item: item.position):
        node = node_by_key[task.task_key or ""]
        response_tasks.append(
            PlannedTaskResponse(
                id=task.id,
                task_key=task.task_key or "",
                title=task.title,
                objective=task.objective,
                position=task.position,
                dependencies=list(node.dependencies),
                required_capabilities=task.required_capabilities,
                agent_name=node.agent_name,
                risk_level=task.risk_level,
                status=task.status,
            )
        )

    return TaskGraphResponse(
        id=graph.id,
        project_id=graph.project_id,
        intent_record_id=graph.intent_record_id,
        name=graph.name,
        version=graph.version,
        status=graph.status,
        objective=graph.objective,
        tasks=response_tasks,
        unknowns=list(plan.unknowns),
        constraints=list(plan.constraints),
        risks=list(plan.risks),
    )


@app.get(
    "/api/v1/projects/{project_id}/state",
    response_model=ProjectStateResponse,
)
async def get_project_state(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ProjectStateResponse:
    state = await session.scalar(
        select(ProjectStateModel).where(ProjectStateModel.project_id == project_id)
    )
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project state not found",
        )
    return ProjectStateResponse(
        project_id=state.project_id,
        status=state.status,
        phase=state.phase,
        version=state.version,
        state=state.state_json,
    )




@app.post(
    "/api/v1/projects/{project_id}/workflows/{workflow_id}/replan",
    status_code=status.HTTP_201_CREATED,
    response_model=ReplanResponse,
)
async def replan_failed_workflow_endpoint(
    project_id: UUID,
    workflow_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ReplanResponse:
    project = await session.scalar(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    workflow = await session.scalar(
        select(WorkflowModel).where(
            WorkflowModel.id == workflow_id,
            WorkflowModel.project_id == project_id,
        )
    )
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    runtime = get_agent_runtime()
    try:
        graph, _, decision = await replan_failed_workflow(
            session,
            project=project,
            workflow=workflow,
            capability_registry=runtime.capabilities,
            contracts=runtime.contracts.all(),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ReplanResponse(
        task_graph_id=graph.id,
        project_id=project_id,
        source_workflow_id=workflow_id,
        version=graph.version,
        status=graph.status,
        failed_task_ids=[UUID(task_id) for task_id in decision.failed_task_ids],
        impacted_task_ids=[UUID(task_id) for task_id in decision.impacted_task_ids],
        reassignments=[
            AgentReassignmentResponse(
                task_id=UUID(item.task_id),
                previous_agent=item.previous_agent,
                new_agent=item.new_agent,
                reason=item.reason,
            )
            for item in decision.reassignments
        ],
    )

@app.get(
    "/api/v1/projects/{project_id}/recovery",
    response_model=RecoveryMetricsResponse,
)
async def get_recovery_metrics(
    project_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> RecoveryMetricsResponse:
    project = await session.scalar(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    metrics = await collect_recovery_metrics(session, project_id=project_id)
    return RecoveryMetricsResponse(
        project_id=project_id,
        started=metrics.started,
        resolved=metrics.resolved,
        repeated_failures=metrics.repeated_failures,
        escalated=metrics.escalated,
        failed_to_start=metrics.failed_to_start,
        terminal_attempts=metrics.terminal_attempts,
        resolved_ratio=metrics.resolved_ratio,
        latest_outcome=metrics.latest_outcome,
        strategy_counts=metrics.strategy_counts,
    )


@app.post(
    "/api/v1/projects/{project_id}/workflows/{workflow_id}/recovery/decision",
    response_model=RecoveryDecisionResponse,
)
async def decide_recovery(
    project_id: UUID,
    workflow_id: UUID,
    payload: RecoveryDecisionRequest,
    session: AsyncSession = Depends(get_session),
    operator: OperatorIdentity = Depends(require_operator),
) -> RecoveryDecisionResponse:
    operator.require_permission("recovery:approve")
    project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id))
    workflow = await session.scalar(
        select(WorkflowModel).where(
            WorkflowModel.id == workflow_id,
            WorkflowModel.project_id == project_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    if workflow.status != "FAILED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Recovery decisions require a failed workflow; current status is {workflow.status}",
        )

    escalation = await session.scalar(
        select(EventModel)
        .where(
            EventModel.project_id == project_id,
            EventModel.aggregate_type == "WORKFLOW",
            EventModel.aggregate_id == workflow.id,
            EventModel.type == "RecoveryEscalated",
        )
        .order_by(EventModel.occurred_at.desc())
        .limit(1)
    )
    if escalation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No pending recovery escalation exists for this workflow",
        )

    escalation_payload = escalation.payload or {}
    current_attempt = int(escalation_payload.get("current_attempt", 0))
    if current_attempt >= settings.recovery_max_attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recovery attempt budget is exhausted",
        )

    if not payload.approved:
        session.add(
            EventModel(
                project_id=project_id,
                type="RecoveryRejected",
                actor_type="OPERATOR",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={
                    "reason": payload.reason or "Recovery rejected by human decision",
                    "current_attempt": current_attempt,
                    "operator_subject": operator.subject,
                    "operator_role": operator.role,
                },
            )
        )
        state = await session.scalar(
            select(ProjectStateModel).where(ProjectStateModel.project_id == project_id)
        )
        if state is not None:
            state.status = "FAILED"
            state.phase = "RECOVERY_REJECTED"
            state.version += 1
        await session.commit()
        return RecoveryDecisionResponse(
            project_id=project_id,
            workflow_id=workflow_id,
            decision="REJECTED",
            strategy=None,
            replacement_workflow_id=None,
            message=payload.reason or "Recovery rejected by human decision",
        )

    failure_category = str(
        escalation_payload.get("failure_category")
        or classify_failure(str(escalation_payload.get("error_message", ""))).value
    )
    if payload.strategy is None:
        history_events = list(
            await session.scalars(
                select(EventModel)
                .where(
                    EventModel.project_id == project_id,
                    EventModel.type.in_(
                        (
                            "RecoveryStarted",
                            "RecoveryResolved",
                            "RecoveryRepeatedFailure",
                            "RecoveryEscalated",
                            "RecoveryFailed",
                        )
                    ),
                )
                .order_by(EventModel.occurred_at.desc())
                .limit(50)
            )
        )
        try:
            category_enum = FailureCategory(failure_category)
        except ValueError:
            category_enum = classify_failure(
                str(escalation_payload.get("error_message", ""))
            )
        strategy = RecoveryStrategySelector().select(
            category=category_enum,
            observations=observations_from_events(history_events),
        ).strategy
    else:
        strategy = payload.strategy

    recovery_root = str(
        escalation_payload.get("recovery_root_workflow_id") or workflow.id
    )
    session.add(
        EventModel(
            project_id=project_id,
            type="RecoveryApproved",
            actor_type="OPERATOR",
            aggregate_type="WORKFLOW",
            aggregate_id=workflow.id,
            payload={
                "reason": payload.reason or "Recovery approved by human decision",
                "current_attempt": current_attempt,
                "strategy": strategy.value,
                "operator_subject": operator.subject,
                "operator_role": operator.role,
                "failure_category": failure_category,
            },
        )
    )
    await session.flush()

    try:
        runtime = get_agent_runtime()
        result = await start_recovery_workflow(
            session,
            project=project,
            workflow=workflow,
            run_id=str(workflow.temporal_run_id or ""),
            error_message=str(escalation_payload.get("error_message", "")),
            recovery_attempt=current_attempt + 1,
            recovery_root_workflow_id=recovery_root,
            failure_category=failure_category,
            strategy=strategy,
            runtime=runtime,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        session.add(
            EventModel(
                project_id=project_id,
                type="RecoveryFailed",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={
                    "recovery_attempt": current_attempt + 1,
                    "failure_category": failure_category,
                    "strategy": strategy.value,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to start the approved recovery workflow",
        ) from exc

    return RecoveryDecisionResponse(
        project_id=project_id,
        workflow_id=workflow_id,
        decision="APPROVED",
        strategy=result.strategy,
        replacement_workflow_id=result.replacement_workflow_id,
        message="Approved recovery workflow started",
    )


@app.post(
    "/api/v1/projects/{project_id}/workflows/{workflow_id}/recovery/rollback",
    response_model=RecoveryRollbackResponse,
)
async def rollback_recovery(
    project_id: UUID,
    workflow_id: UUID,
    payload: RecoveryRollbackRequest,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
    operator: OperatorIdentity = Depends(require_operator),
) -> RecoveryRollbackResponse:
    operator.require_permission("recovery:rollback")
    project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id))
    workflow = await session.scalar(
        select(WorkflowModel).where(
            WorkflowModel.id == workflow_id,
            WorkflowModel.project_id == project_id,
        )
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    if workflow.workflow_type != "RECOVERY":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only recovery workflows can be rolled back",
        )

    recovery_started = await session.scalar(
        select(EventModel)
        .where(
            EventModel.project_id == project_id,
            EventModel.aggregate_type == "WORKFLOW",
            EventModel.aggregate_id == workflow.id,
            EventModel.type == "WorkflowRecoveryStarted",
        )
        .order_by(EventModel.occurred_at.desc())
        .limit(1)
    )
    recovery_payload = recovery_started.payload if recovery_started is not None else {}
    source_workflow_raw = recovery_payload.get("source_workflow_id")
    source_workflow_id = UUID(source_workflow_raw) if source_workflow_raw else None

    if workflow.status in {"STARTING", "RUNNING"} and workflow.temporal_workflow_id:
        try:
            handle = temporal_client.get_workflow_handle(workflow.temporal_workflow_id)
            await handle.cancel()
        except Exception:
            pass

    workflow.status = "ROLLED_BACK"
    workflow.completed_at = workflow.completed_at or datetime.now(UTC)

    graph = None
    if workflow.task_graph_id is not None:
        graph = await session.scalar(
            select(TaskGraphModel).where(TaskGraphModel.id == workflow.task_graph_id)
        )
        if graph is not None:
            graph.status = "ROLLED_BACK"

    tasks = list(
        await session.scalars(select(TaskModel).where(TaskModel.workflow_id == workflow.id))
    )
    for task in tasks:
        task.status = "ROLLED_BACK"

    state = await session.scalar(
        select(ProjectStateModel).where(ProjectStateModel.project_id == project_id)
    )
    if state is not None:
        state.status = "WAITING_HUMAN"
        state.phase = "RECOVERY_ROLLED_BACK"
        state.version += 1
        if source_workflow_id is not None:
            source_workflow = await session.scalar(
                select(WorkflowModel).where(
                    WorkflowModel.id == source_workflow_id,
                    WorkflowModel.project_id == project_id,
                )
            )
            if source_workflow is not None and source_workflow.task_graph_id is not None:
                state.state_json = {
                    **state.state_json,
                    "task_graph_id": str(source_workflow.task_graph_id),
                    "rolled_back_recovery_workflow_id": str(workflow.id),
                }

    session.add(
        EventModel(
            project_id=project_id,
            type="RecoveryRolledBack",
            actor_type="OPERATOR",
            aggregate_type="WORKFLOW",
            aggregate_id=workflow.id,
            payload={
                "source_workflow_id": str(source_workflow_id)
                if source_workflow_id is not None
                else None,
                "task_graph_id": str(graph.id) if graph is not None else None,
                "reason": payload.reason,
                "operator_subject": operator.subject,
                "operator_role": operator.role,
            },
        )
    )
    session.add(
        EventModel(
            project_id=project_id,
            type="RecoveryControlPlaneRollback",
            actor_type="SYSTEM",
            aggregate_type="WORKFLOW",
            aggregate_id=workflow.id,
            payload={
                "source_workflow_id": str(source_workflow_id)
                if source_workflow_id is not None
                else None,
                "reason": payload.reason,
                "external_side_effects_reversed": False,
                "operator_subject": operator.subject,
                "operator_role": operator.role,
            },
        )
    )
    await MemoryStore().remember(
        session,
        project_id=project_id,
        task_id=None,
        kind="RECOVERY_ROLLBACK",
        content=(
            f"Recovery workflow {workflow.id} was rolled back at the control-plane "
            "level; external side effects are not assumed to be reversible."
        ),
        importance=99,
        source_type="RECOVERY_GOVERNANCE",
        source_id=workflow.id,
        metadata={
            "source_workflow_id": str(source_workflow_id)
            if source_workflow_id is not None
            else None,
            "reason": payload.reason,
            "external_side_effects_reversed": False,
        },
    )
    await session.commit()

    return RecoveryRollbackResponse(
        project_id=project_id,
        recovery_workflow_id=workflow_id,
        source_workflow_id=source_workflow_id,
        status="ROLLED_BACK",
        reason=payload.reason,
    )


@app.post(
    "/api/v1/projects/{project_id}/tasks",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskResponse,
)
async def create_task(
    project_id: UUID,
    payload: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> TaskModel:
    project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task = TaskModel(
        project_id=project_id,
        title=payload.title,
        objective=payload.objective,
        risk_level=payload.risk_level,
    )
    session.add(task)
    await session.flush()

    session.add(
        EventModel(
            project_id=project_id,
            type="TaskCreated",
            actor_type="SYSTEM",
            aggregate_type="TASK",
            aggregate_id=task.id,
            payload={"title": task.title, "risk_level": task.risk_level},
        )
    )
    await session.commit()
    await session.refresh(task)
    return task


@app.post(
    "/api/v1/projects/{project_id}/tasks/{task_id}/approval",
    response_model=TaskApprovalResponse,
)
async def decide_task_approval(
    project_id: UUID,
    task_id: UUID,
    payload: TaskApprovalRequest,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
    operator: OperatorIdentity = Depends(require_operator),
) -> TaskApprovalResponse:
    operator.require_permission("task:approve")

    task = await session.scalar(
        select(TaskModel).where(
            TaskModel.id == task_id,
            TaskModel.project_id == project_id,
        )
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    if task.workflow_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is not attached to a workflow",
        )
    if task.status != "WAITING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task approval requires WAITING_APPROVAL status; current status is {task.status}",
        )

    workflow = await session.scalar(
        select(WorkflowModel).where(
            WorkflowModel.id == task.workflow_id,
            WorkflowModel.project_id == project_id,
        )
    )
    if workflow is None or not workflow.temporal_workflow_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task workflow is not running with a Temporal workflow id",
        )

    reason = payload.reason or (
        "Task approved by operator"
        if payload.approved
        else "Task rejected by operator"
    )
    task.status = "APPROVED" if payload.approved else "REJECTED"

    session.add(
        EventModel(
            project_id=project_id,
            type="TaskApprovalGranted" if payload.approved else "TaskApprovalRejected",
            actor_type="OPERATOR",
            actor_id=None,
            aggregate_type="TASK",
            aggregate_id=task.id,
            payload={
                "workflow_id": str(workflow.id),
                "operator_subject": operator.subject,
                "operator_role": operator.role,
                "reason": reason,
            },
        )
    )

    state = await session.scalar(
        select(ProjectStateModel).where(
            ProjectStateModel.project_id == project_id
        )
    )
    if state is not None and payload.approved:
        state.status = "RUNNING"
        state.phase = "EXECUTION"
        state.version += 1

    await session.commit()

    handle = temporal_client.get_workflow_handle(workflow.temporal_workflow_id)
    try:
        if payload.approved:
            await handle.signal("approve_task", str(task.id))
        else:
            await handle.signal("reject_task", str(task.id), reason)
    except Exception as exc:
        task.status = "WAITING_APPROVAL"
        session.add(
            EventModel(
                project_id=project_id,
                type="TaskApprovalSignalFailed",
                actor_type="SYSTEM",
                aggregate_type="TASK",
                aggregate_id=task.id,
                payload={
                    "operator_subject": operator.subject,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
        )
        await session.commit()

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Temporal workflow could not receive the approval decision",
        ) from exc

    return TaskApprovalResponse(
        project_id=project_id,
        task_id=task.id,
        workflow_id=workflow.id,
        decision="APPROVED" if payload.approved else "REJECTED",
        reason=reason,
        status=task.status,
    )


@app.post(
    "/api/v1/projects/{project_id}/workflows",
    status_code=status.HTTP_201_CREATED,
    response_model=WorkflowResponse,
)
async def create_and_start_workflow(
    project_id: UUID,
    payload: WorkflowCreate,
    session: AsyncSession = Depends(get_session),
    temporal_client: Client = Depends(get_temporal_client),
) -> WorkflowModel:
    project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    task_graph = None
    if payload.task_graph_id is not None:
        task_graph = await session.scalar(
            select(TaskGraphModel).where(
                TaskGraphModel.id == payload.task_graph_id,
                TaskGraphModel.project_id == project_id,
            )
        )
        if task_graph is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task graph not found",
            )
        if task_graph.status not in {"READY", "PLANNED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task graph is not executable in status {task_graph.status}",
            )
        tasks = list(
            await session.scalars(
                select(TaskModel)
                .where(
                    TaskModel.project_id == project_id,
                    TaskModel.task_graph_id == task_graph.id,
                )
                .order_by(TaskModel.position.asc())
            )
        )
        if not tasks:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task graph contains no tasks",
            )
        requested_task_ids = [task.id for task in tasks]
    else:
        requested_task_ids = list(dict.fromkeys(payload.task_ids))
        task_rows = {
            task.id: task
            for task in (
                await session.scalars(
                    select(TaskModel).where(
                        TaskModel.project_id == project_id,
                        TaskModel.id.in_(requested_task_ids),
                    )
                )
            )
        }
        if len(task_rows) != len(requested_task_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Every task must exist and belong to the project",
            )
        tasks = [task_rows[task_id] for task_id in requested_task_ids]

    workflow = WorkflowModel(
        project_id=project_id,
        task_graph_id=task_graph.id if task_graph is not None else None,
        name=payload.name,
        workflow_type=payload.workflow_type,
        status="STARTING",
    )
    session.add(workflow)
    await session.flush()

    for task in tasks:
        if task.workflow_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Task {task.id} is already assigned to a workflow",
            )
        task.workflow_id = workflow.id

    temporal_workflow_id = f"titan-workflow-{workflow.id}"
    workflow.temporal_workflow_id = temporal_workflow_id
    if task_graph is not None:
        task_graph.status = "RUNNING"

    session.add(
        EventModel(
            project_id=project_id,
            type="WorkflowCreated",
            actor_type="SYSTEM",
            aggregate_type="WORKFLOW",
            aggregate_id=workflow.id,
            payload={"task_count": len(tasks), "workflow_type": workflow.workflow_type},
        )
    )
    await session.commit()

    requested_ids = tuple(str(task.id) for task in tasks)
    dependency_rows = list(
        await session.execute(
            select(
                task_dependencies.c.task_id,
                task_dependencies.c.depends_on_task_id,
            ).where(
                task_dependencies.c.task_id.in_([task.id for task in tasks])
            )
        )
    )
    requested_id_set = set(requested_ids)
    dependency_map: dict[str, list[str]] = {
        task_id: []
        for task_id in requested_ids
    }
    for task_id, dependency_id in dependency_rows:
        dependency_str = str(dependency_id)
        if dependency_str not in requested_id_set:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Task {task_id} has a dependency outside the requested "
                    "workflow task set"
                ),
            )
        dependency_map[str(task_id)].append(dependency_str)

    history_rows = list(
        await session.scalars(
            select(EventModel)
            .where(
                EventModel.project_id == project_id,
                EventModel.type == "ModelUsageRecorded",
                EventModel.aggregate_type == "TASK",
                EventModel.aggregate_id.in_([task.id for task in tasks]),
            )
            .order_by(EventModel.created_at.desc())
        )
    )
    usage_history: dict[tuple[UUID, str], list[tuple[float | None, int | None]]] = {}
    for event in history_rows:
        payload = event.payload or {}
        model = str(payload.get("model") or "")
        if not model:
            continue
        usage = payload.get("usage") or {}
        cost = usage.get("estimated_cost")
        duration = payload.get("duration_ms")
        if duration is None:
            duration = payload.get("elapsed_ms")
        try:
            parsed_cost = float(cost) if cost is not None else None
        except (TypeError, ValueError):
            parsed_cost = None
        try:
            parsed_duration = int(duration) if duration is not None else None
        except (TypeError, ValueError):
            parsed_duration = None
        key = (event.aggregate_id, model)
        usage_history.setdefault(key, []).append(
            (parsed_cost, parsed_duration)
        )

    owner_agent_ids = {
        task.owner_agent_id
        for task in tasks
        if task.owner_agent_id is not None
    }
    agent_rows = (
        list(
            await session.scalars(
                select(AgentModel).where(AgentModel.id.in_(owner_agent_ids))
            )
        )
        if owner_agent_ids
        else []
    )
    agents_by_id = {agent.id: agent for agent in agent_rows}
    runtime = get_agent_runtime()

    task_agents: list[tuple[str, str]] = []
    used_agents: dict[str, int] = {}
    task_profiles: list[WorkflowTaskProfile] = []
    precompleted_task_ids = tuple(
        str(task.id)
        for task in tasks
        if task.status == "COMPLETED"
    )

    for task in tasks:
        if task.owner_agent_id is None:
            agent_name = "general-executor"
            contract = runtime.contracts.resolve(agent_name)
            metadata = {
                "max_concurrency": contract.max_concurrency,
                "minimum_quality_tier": contract.minimum_quality_tier,
                "scheduling_priority": contract.scheduling_priority,
                "model": contract.model,
            }
        else:
            agent = agents_by_id.get(task.owner_agent_id)
            if agent is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Assigned agent for task {task.id} is not available",
                )
            agent_name = agent.name
            metadata = agent.metadata_json

        task_id = str(task.id)
        task_agents.append((task_id, agent_name))

        try:
            capacity = max(1, int(metadata.get("max_concurrency", 1)))
        except (TypeError, ValueError):
            capacity = 1
        used_agents[agent_name] = capacity

        try:
            minimum_quality_tier = max(0, int(metadata.get("minimum_quality_tier", 1)))
        except (TypeError, ValueError):
            minimum_quality_tier = 1

        try:
            priority = int(metadata.get("scheduling_priority", 0))
        except (TypeError, ValueError):
            priority = 0

        preferred_model = str(metadata.get("model") or "local")
        provider_available = True
        estimated_cost = 0.0
        expected_duration_ms = 0
        try:
            selection = runtime.model_router.select(
                ModelSelectionRequest(
                    preferred_model=preferred_model,
                    minimum_quality_tier=minimum_quality_tier,
                    budget=ModelBudget(
                        max_input_tokens=settings.model_max_input_tokens,
                        max_output_tokens=settings.model_max_output_tokens,
                        max_cost=0.0,
                    ),
                )
            )
            fallback_estimated_cost = runtime.model_router.estimate_cost(
                selection.route,
                {
                    "input_tokens": settings.model_max_input_tokens,
                    "output_tokens": settings.model_max_output_tokens,
                },
            )
            history = usage_history.get((task.id, selection.route.model), ())[:5]
            observed_costs = [
                value
                for value, _ in history
                if value is not None
            ]
            observed_durations = [
                value
                for _, value in history
                if value is not None
            ]
            estimated_cost = (
                sum(observed_costs) / len(observed_costs)
                if observed_costs
                else fallback_estimated_cost
            )
            expected_duration_ms = (
                round(sum(observed_durations) / len(observed_durations))
                if observed_durations
                else 0
            )
        except (BudgetExceeded, KeyError, LookupError, ValueError):
            provider_available = False

        task_profiles.append(
            WorkflowTaskProfile(
                task_id=task_id,
                risk_level=task.risk_level,
                minimum_quality_tier=minimum_quality_tier,
                estimated_cost=estimated_cost,
                expected_duration_ms=expected_duration_ms,
                priority=priority,
                provider_available=provider_available,
            )
        )

    request = WorkflowInput(
        workflow_id=str(workflow.id),
        project_id=str(project_id),
        task_ids=requested_ids,
        dependencies=tuple(
            (
                task_id,
                tuple(sorted(dependency_map[task_id])),
            )
            for task_id in requested_ids
        ),
        task_agents=tuple(task_agents),
        agent_capacities=tuple(sorted(used_agents.items())),
        task_profiles=tuple(task_profiles),
        max_project_cost=settings.orchestration_max_cost,
        precompleted_task_ids=precompleted_task_ids,
    )

    try:
        preflight_schedule = DependencyAwareScheduler().build(
            requested_ids,
            tuple(
                (
                    task_id,
                    tuple(sorted(dependency_map[task_id])),
                )
                for task_id in requested_ids
            ),
            task_agents=tuple(task_agents),
            agent_capacities=tuple(sorted(used_agents.items())),
            task_profiles=tuple(
                TaskSchedulingProfile(
                    task_id=profile.task_id,
                    risk_level=profile.risk_level,
                    minimum_quality_tier=profile.minimum_quality_tier,
                    estimated_cost=profile.estimated_cost,
                    expected_duration_ms=profile.expected_duration_ms,
                    priority=profile.priority,
                    provider_available=profile.provider_available,
                )
                for profile in task_profiles
            ),
            max_project_cost=settings.orchestration_max_cost,
            precompleted_task_ids=precompleted_task_ids,
        )
    except TaskScheduleError as exc:
        for task in tasks:
            task.workflow_id = None
        workflow.status = "FAILED"
        if task_graph is not None:
            task_graph.status = "READY"
        session.add(
            EventModel(
                project_id=project_id,
                type="WorkflowSchedulingRejected",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow rejected by orchestration policy: {exc}",
        ) from exc

    try:
        await temporal_client.start_workflow(
            TitanWorkflow.run,
            request,
            id=temporal_workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except Exception as exc:
        for task in tasks:
            task.workflow_id = None
        workflow.status = "FAILED"
        if task_graph is not None:
            task_graph.status = "READY"
        session.add(
            EventModel(
                project_id=project_id,
                type="WorkflowStartFailed",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=workflow.id,
                payload={"error_message": str(exc)},
            )
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to start workflow execution",
        ) from exc

    session.add(
        EventModel(
            project_id=project_id,
            type="WorkflowExecutionRequested",
            actor_type="SYSTEM",
            aggregate_type="WORKFLOW",
            aggregate_id=workflow.id,
            payload={
                "temporal_workflow_id": temporal_workflow_id,
                "task_count": len(tasks),
                "dependency_edge_count": sum(
                    len(items)
                    for items in dependency_map.values()
                ),
                "estimated_schedule_cost": preflight_schedule.estimated_cost,
                "estimated_makespan_ms": preflight_schedule.estimated_makespan_ms,
                "max_project_cost": settings.orchestration_max_cost,
                "task_profile_count": len(task_profiles),
            },
        )
    )
    await session.commit()
    await session.refresh(workflow)
    return workflow
