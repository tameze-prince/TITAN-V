import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from titan.api.app import app
from titan.persistence.database import SessionFactory
from titan.persistence.models import EventModel, ProjectModel, TaskModel, WorkflowModel


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


@pytest.mark.asyncio
async def test_control_plane_exposes_pending_recovery_actions() -> None:
    name = f"recovery-actions-{uuid4()}"

    async with SessionFactory() as session:
        project = ProjectModel(name=name, objective="Exercise governed recovery actions")
        session.add(project)
        await session.flush()

        failed_workflow = WorkflowModel(
            project_id=project.id,
            name="Primary execution",
            workflow_type="GENERIC",
            status="FAILED",
        )
        active_recovery = WorkflowModel(
            project_id=project.id,
            name="Recovery 1 for primary",
            workflow_type="RECOVERY",
            status="RUNNING",
        )
        session.add_all([failed_workflow, active_recovery])
        await session.flush()

        session.add(
            EventModel(
                project_id=project.id,
                type="RecoveryEscalated",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=failed_workflow.id,
                payload={
                    "reason": "Human approval required",
                    "current_attempt": 1,
                    "failure_category": "PROVIDER",
                },
            )
        )
        session.add(
            EventModel(
                project_id=project.id,
                type="WorkflowRecoveryStarted",
                actor_type="SYSTEM",
                aggregate_type="WORKFLOW",
                aggregate_id=active_recovery.id,
                payload={"source_workflow_id": str(failed_workflow.id)},
            )
        )
        await session.commit()
        project_id = project.id

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/v1/control-plane/projects/{project_id}"
        )

    assert response.status_code == 200
    actions = response.json()["recovery_actions"]
    assert {item["action"] for item in actions} == {
        "APPROVE_OR_REJECT_RECOVERY",
        "ROLLBACK_RECOVERY",
    }

    async with SessionFactory() as session:
        project = await session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        assert project is not None
        await session.delete(project)
        await session.commit()


@pytest.mark.asyncio
async def test_control_plane_lists_waiting_task_approval() -> None:
    name = f"task-approval-{uuid4()}"

    async with SessionFactory() as session:
        project = ProjectModel(name=name, objective="Exercise task approval")
        session.add(project)
        await session.flush()

        workflow = WorkflowModel(
            project_id=project.id,
            name="Approval workflow",
            workflow_type="GENERIC",
            status="RUNNING",
            temporal_workflow_id="temporal-approval-test",
        )
        session.add(workflow)
        await session.flush()

        task = TaskModel(
            project_id=project.id,
            workflow_id=workflow.id,
            title="Approve deployment",
            objective="Deploy the staging candidate",
            status="WAITING_APPROVAL",
            risk_level="R2",
            approval_requirement="NONE",
        )
        session.add(task)
        await session.commit()
        project_id = project.id

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/api/v1/control-plane/projects/{project_id}"
        )

    assert response.status_code == 200
    actions = response.json()["task_approval_actions"]
    assert len(actions) == 1
    assert actions[0]["risk_level"] == "R2"
    assert actions[0]["task_id"] == str(task.id)

    async with SessionFactory() as session:
        project = await session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )
        assert project is not None
        await session.delete(project)
        await session.commit()
