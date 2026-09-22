import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from titan.api.app import app
from titan.integrations.temporal.client import get_temporal_client
from titan.persistence.database import SessionFactory
from titan.persistence.models import EventModel, ProjectModel, TaskModel, WorkflowModel


pytestmark = pytest.mark.skipif(
    os.getenv("TITAN_RUN_INTEGRATION") != "1",
    reason="Integration tests require TITAN_RUN_INTEGRATION=1 and PostgreSQL",
)


class FakeTemporalClient:
    def __init__(self) -> None:
        self.started: list[dict] = []

    async def start_workflow(self, workflow, request, *, id: str, task_queue: str):
        self.started.append(
            {
                "workflow": workflow,
                "request": request,
                "id": id,
                "task_queue": task_queue,
            }
        )


@pytest.mark.asyncio
async def test_create_and_start_workflow_persists_graph() -> None:
    project_id = uuid4()
    task_ids = (uuid4(), uuid4())
    fake_temporal = FakeTemporalClient()

    async with SessionFactory() as session:
        session.add(ProjectModel(id=project_id, name=f"workflow-project-{project_id}"))
        session.add_all(
            [
                TaskModel(
                    id=task_ids[0],
                    project_id=project_id,
                    title="Bootstrap task A",
                    objective="Validate workflow graph",
                ),
                TaskModel(
                    id=task_ids[1],
                    project_id=project_id,
                    title="Bootstrap task B",
                    objective="Validate workflow graph",
                ),
            ]
        )
        await session.commit()

    app.dependency_overrides[get_temporal_client] = lambda: fake_temporal

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/api/v1/projects/{project_id}/workflows",
                json={
                    "name": "Core workflow",
                    "workflow_type": "CORE",
                    "task_ids": [str(task_id) for task_id in task_ids],
                },
            )
    finally:
        app.dependency_overrides.pop(get_temporal_client, None)

    assert response.status_code == 201
    assert len(fake_temporal.started) == 1
    assert fake_temporal.started[0]["task_queue"] == "titan-core"

    async with SessionFactory() as session:
        workflow_id = response.json()["id"]
        workflow = await session.scalar(
            select(WorkflowModel).where(WorkflowModel.id == workflow_id)
        )
        tasks = list(
            await session.scalars(
                select(TaskModel)
                .where(TaskModel.project_id == project_id)
                .order_by(TaskModel.created_at)
            )
        )
        events = list(
            await session.scalars(
                select(EventModel)
                .where(EventModel.project_id == project_id)
                .order_by(EventModel.occurred_at)
            )
        )

        assert workflow is not None
        assert workflow.status == "STARTING"
        assert workflow.temporal_workflow_id is not None
        assert [task.workflow_id for task in tasks] == [workflow.id, workflow.id]
        assert any(event.type == "WorkflowExecutionRequested" for event in events)

        await session.delete(workflow)
        project = await session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        if project is not None:
            await session.delete(project)
        await session.commit()
