import os
from uuid import uuid4

import pytest
from sqlalchemy import select

from titan.persistence.database import SessionFactory
from titan.persistence.models import ProjectModel, TaskModel


pytestmark = pytest.mark.skipif(
    os.getenv("TITAN_RUN_INTEGRATION") != "1",
    reason="Integration tests require TITAN_RUN_INTEGRATION=1 and PostgreSQL",
)


@pytest.mark.asyncio
async def test_workflow_task_graph_persistence() -> None:
    project_id = uuid4()
    task_id = uuid4()

    async with SessionFactory() as session:
        project = ProjectModel(id=project_id, name=f"workflow-project-{project_id}")
        session.add(project)
        await session.flush()

        task = TaskModel(
            id=task_id,
            project_id=project_id,
            title="Bootstrap task",
            objective="Validate workflow graph persistence",
            status="PENDING",
        )
        session.add(task)
        await session.commit()

    async with SessionFactory() as session:
        project = await session.scalar(select(ProjectModel).where(ProjectModel.id == project_id))
        task = await session.scalar(select(TaskModel).where(TaskModel.id == task_id))
        assert project is not None
        assert task is not None
        assert task.workflow_id is None

        await session.delete(project)
        await session.commit()
