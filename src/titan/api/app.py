from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from titan import __version__
from titan.config import settings
from titan.integrations.temporal.client import get_temporal_client
from titan.persistence.database import close_database, get_session
from titan.persistence.models import EventModel, IntentRecordModel, ProjectModel, TaskModel, WorkflowModel
from titan.runtime.intent import IntentCompiler, IntentRepresentation
from titan.runtime.memory import MemoryStore
from titan.runtime.model_router import ModelBudget, ModelSelectionRequest
from titan.runtime.service import get_agent_runtime
from titan.workflows.contracts import WorkflowInput
from titan.workflows.runtime import TitanWorkflow


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
    title: str
    objective: str
    status: str
    risk_level: str

    model_config = {"from_attributes": True}


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    workflow_type: str = Field(default="GENERIC", min_length=1, max_length=64)
    task_ids: list[UUID] = Field(min_length=1, max_length=100)


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


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await close_database()


app = FastAPI(title="TITAN V.", version=__version__, lifespan=lifespan)


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
        EventModel(
            project_id=project.id,
            type="ProjectCreated",
            actor_type="SYSTEM",
            aggregate_type="PROJECT",
            aggregate_id=project.id,
            payload={"name": project.name},
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

    requested_task_ids = set(payload.task_ids)
    tasks = list(
        await session.scalars(
            select(TaskModel).where(
                TaskModel.project_id == project_id,
                TaskModel.id.in_(requested_task_ids),
            )
        )
    )
    if len(tasks) != len(requested_task_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Every task must exist and belong to the project",
        )

    workflow = WorkflowModel(
        project_id=project_id,
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

    request = WorkflowInput(
        workflow_id=str(workflow.id),
        project_id=str(project_id),
        task_ids=tuple(str(task.id) for task in tasks),
    )

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
            },
        )
    )
    await session.commit()
    await session.refresh(workflow)
    return workflow
