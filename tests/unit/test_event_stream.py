from datetime import UTC, datetime
from uuid import uuid4

from titan.persistence.models import EventModel
from titan.runtime.event_stream import _cursor_value, _serialize_event


def test_event_cursor_is_resumable_and_ordered() -> None:
    event_id = uuid4()
    event = EventModel(
        id=event_id,
        project_id=uuid4(),
        type="TaskCompleted",
        actor_type="SYSTEM",
        aggregate_type="TASK",
        aggregate_id=uuid4(),
        occurred_at=datetime(2026, 9, 28, 9, 0, tzinfo=UTC),
        payload={"task_id": "abc"},
        schema_version=1,
    )

    cursor = _cursor_value(event)

    assert cursor.startswith("2026-09-28T09:00:00+00:00|")
    assert str(event_id) in cursor


def test_event_serialization_is_json_safe() -> None:
    event = EventModel(
        id=uuid4(),
        project_id=uuid4(),
        type="RecoveryApproved",
        actor_type="OPERATOR",
        aggregate_type="WORKFLOW",
        aggregate_id=uuid4(),
        occurred_at=datetime(2026, 9, 28, 9, 1, tzinfo=UTC),
        payload={"operator_subject": "operator-1"},
        schema_version=1,
    )

    payload = _serialize_event(event)

    assert '"type":"RecoveryApproved"' in payload
    assert '"actor_type":"OPERATOR"' in payload
    assert '"operator_subject":"operator-1"' in payload
