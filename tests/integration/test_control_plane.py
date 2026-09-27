import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from titan.api.app import app
from titan.persistence.database import SessionFactory
from titan.persistence.models import ProjectModel


pytestmark = pytest.mark.skipif(
    os.getenv("TITAN_RUN_INTEGRATION") != "1",
    reason="Integration tests require TITAN_RUN_INTEGRATION=1 and PostgreSQL",
)


@pytest.mark.asyncio
async def test_control_plane_project_overview_exposes_operator_state() -> None:
    name = f"control-plane-{uuid4()}"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        created = await client.post(
            "/api/v1/projects",
            json={"name": name, "objective": "Expose operator state"},
        )
        assert created.status_code == 201
        project_id = created.json()["id"]

        overview = await client.get(f"/api/v1/control-plane/projects/{project_id}")
        assert overview.status_code == 200

        payload = overview.json()
        assert payload["project"]["id"] == project_id
        assert payload["project"]["current_phase"] == "DISCOVERY"
        assert payload["state"]["phase"] == "DISCOVERY"
        assert payload["task_counts"]["total"] == 0
        assert payload["workflow_counts"]["total"] == 0
        assert payload["pending_human_decisions"] == 0
        assert payload["pending_task_approvals"] == 0
        assert payload["latest_task_graph"] is None

        global_overview = await client.get("/api/v1/control-plane/overview")
        assert global_overview.status_code == 200
        assert global_overview.json()["projects"]["total"] >= 1

    async with SessionFactory() as session:
        project = await session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        assert project is not None
        await session.delete(project)
        await session.commit()
