import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from titan.api.app import app
from titan.persistence.database import SessionFactory
from titan.persistence.models import EventModel, ProjectModel

pytestmark = pytest.mark.skipif(
    os.getenv("TITAN_RUN_INTEGRATION") != "1",
    reason="Integration tests require TITAN_RUN_INTEGRATION=1 and PostgreSQL",
)


@pytest.mark.asyncio
async def test_create_project_persists_and_emits_event() -> None:
    name = f"integration-{uuid4()}"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/projects",
            json={"name": name, "objective": "Verify persistence"},
        )

    assert response.status_code == 201
    payload = response.json()

    async with SessionFactory() as session:
        project = await session.scalar(select(ProjectModel).where(ProjectModel.name == name))
        assert project is not None
        assert str(project.id) == payload["id"]
        assert project.objective == "Verify persistence"
        assert project.status == "ACTIVE"

        event = await session.scalar(
            select(EventModel)
            .where(
                EventModel.project_id == project.id,
                EventModel.type == "ProjectCreated",
            )
            .order_by(EventModel.occurred_at.desc())
        )
        assert event is not None
        assert event.aggregate_id == project.id

        await session.delete(project)
        await session.commit()
