from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from titan.runtime.explainability import (
    _stage_for_event,
    _summarize_event,
    build_project_explainability_trace,
)


def test_event_stage_mapping_is_deterministic() -> None:
    assert _stage_for_event("IntentCompiled") == "INTENT"
    assert _stage_for_event("TaskGraphPlanned") == "PLANNING"
    assert _stage_for_event("WorkflowStarted") == "ORCHESTRATION"
    assert _stage_for_event("TaskCompleted") == "EXECUTION"
    assert _stage_for_event("RecoveryResolved") == "RECOVERY"
    assert _stage_for_event("UnknownThing") == "SYSTEM"


def test_event_summary_prefers_explanatory_payload() -> None:
    event = SimpleNamespace(
        type="RecoveryFailed",
        payload={"error_message": "provider outage"},
    )

    assert _summarize_event(event) == "provider outage"


class _ScalarResult:
    def __init__(self, values):
        self.values = values

    def __iter__(self):
        return iter(self.values)


class _FakeSession:
    def __init__(self, events, decisions):
        self.events = events
        self.decisions = decisions

    async def scalars(self, statement):
        text = str(statement)
        if "governance_decisions" in text:
            return _ScalarResult(self.decisions)
        return _ScalarResult(self.events)


@pytest.mark.asyncio
async def test_explainability_trace_merges_events_and_governance_decisions() -> None:
    project_id = uuid4()
    event = SimpleNamespace(
        id=uuid4(),
        occurred_at=datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
        type="WorkflowStarted",
        actor_type="SYSTEM",
        aggregate_type="WORKFLOW",
        aggregate_id=uuid4(),
        payload={"workflow_id": str(uuid4())},
    )
    decision = SimpleNamespace(
        id=uuid4(),
        created_at=datetime(2026, 9, 27, 12, 0, 1, tzinfo=UTC),
        domain="RECOVERY",
        workflow_id=None,
        policy_version_id=None,
        action="APPROVAL_REQUIRED",
        allowed=False,
        requires_human=True,
        reason="human approval required",
        checks_json=[],
        context_json={},
    )

    trace = await build_project_explainability_trace(
        _FakeSession([event], [decision]),
        project_id=project_id,
    )

    assert len(trace) == 2
    assert trace[0].stage == "ORCHESTRATION"
    assert trace[1].stage == "GOVERNANCE"
