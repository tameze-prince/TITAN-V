import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select

from titan.persistence.database import SessionFactory
from titan.persistence.models import ProjectModel
from titan.runtime.evaluation_service import EvaluationCheck, EvaluationEngine
from titan.runtime.memory import MemoryStore

pytestmark = pytest.mark.skipif(
    os.getenv("TITAN_RUN_INTEGRATION") != "1",
    reason="Persistence tests require TITAN_RUN_INTEGRATION=1 and PostgreSQL",
)


@pytest_asyncio.fixture
async def postgres_session_factory():
    yield SessionFactory


@pytest.mark.asyncio
async def test_memory_store_searches_relevant_project_memory(postgres_session_factory) -> None:
    store = MemoryStore()
    project_id = uuid4()

    async with postgres_session_factory() as session:
        session.add(ProjectModel(id=project_id, name=f"memory-project-{project_id}"))
        await session.flush()

        await store.remember(
            session,
            project_id=project_id,
            task_id=None,
            kind="DECISION",
            content="Temporal is the durable workflow runtime.",
            importance=90,
        )
        await store.remember(
            session,
            project_id=project_id,
            task_id=None,
            kind="NOTE",
            content="Frontend uses Next.js.",
            importance=40,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        await session.commit()

        hits = await store.search(session, project_id=project_id, query="workflow runtime")

        await session.delete(await session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id)
        ))
        await session.commit()

    assert len(hits) == 1
    assert hits[0].kind == "DECISION"
    assert hits[0].importance == 90


@pytest.mark.asyncio
async def test_memory_store_rejects_invalid_importance(postgres_session_factory) -> None:
    store = MemoryStore()
    with pytest.raises(ValueError, match="importance"):
        async with postgres_session_factory() as session:
            await store.remember(
                session,
                project_id=uuid4(),
                task_id=None,
                kind="NOTE",
                content="bad",
                importance=101,
            )


def test_evaluation_engine_scores_checks() -> None:
    engine = EvaluationEngine()
    result = engine.evaluate(
        checks=(
            EvaluationCheck("structured_output", True, "Output matched the schema"),
            EvaluationCheck("artifact", True, "Artifact exists"),
            EvaluationCheck("quality", False, "Required evidence is missing"),
        )
    )

    assert result.passed is False
    assert result.score == pytest.approx(2 / 3)


@pytest.mark.asyncio
async def test_evaluation_engine_persists_and_plans_repair(postgres_session_factory) -> None:
    engine = EvaluationEngine()
    project_id = uuid4()

    async with postgres_session_factory() as session:
        session.add(ProjectModel(id=project_id, name=f"evaluation-project-{project_id}"))
        await session.flush()

        evaluation = await engine.persist(
            session,
            project_id=project_id,
            task_id=None,
            run_id=None,
            result=engine.evaluate(
                checks=(EvaluationCheck("quality", False, "Evidence missing"),)
            ),
        )
        repair = await engine.plan_repair(
            session,
            evaluation_id=evaluation.id,
            task_id=None,
            attempt=1,
            diagnosis="Required evidence was not produced.",
            corrective_action="Collect evidence before finalizing the artifact.",
        )
        await session.commit()

        await session.delete(await session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id)
        ))
        await session.commit()

    assert evaluation.status == "FAILED"
    assert repair.status == "PLANNED"
