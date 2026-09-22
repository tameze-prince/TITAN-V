from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan import __version__
from titan.persistence.database import close_database, get_session
from titan.persistence.models import EventModel, ProjectModel


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    objective: str | None = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    objective: str | None
    status: str
    current_phase: str
    autonomy_level: int

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
