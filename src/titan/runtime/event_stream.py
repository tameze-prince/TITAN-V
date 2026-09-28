import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.database import SessionFactory
from titan.persistence.models import EventModel, ProjectModel
from titan.runtime.operator_auth import OperatorIdentity, require_operator


def _cursor_value(event: EventModel) -> str:
    occurred = event.occurred_at.astimezone(UTC).isoformat()
    return f"{occurred}|{event.id}"


def _serialize_event(event: EventModel) -> str:
    payload = {
        "id": str(event.id),
        "project_id": str(event.project_id) if event.project_id else None,
        "type": event.type,
        "actor_type": event.actor_type,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
        "occurred_at": event.occurred_at.astimezone(UTC).isoformat(),
        "payload": event.payload,
        "schema_version": event.schema_version,
    }
    return json.dumps(payload, separators=(",", ":"), default=str)


async def _get_events_after(
    project_id: UUID,
    cursor: str | None,
    *,
    limit: int = 100,
) -> list[EventModel]:
    async with SessionFactory() as session:
        statement = (
            select(EventModel)
            .where(EventModel.project_id == project_id)
            .order_by(EventModel.occurred_at.asc(), EventModel.id.asc())
            .limit(limit)
        )

        if cursor:
            try:
                cursor_time_raw, cursor_id_raw = cursor.rsplit("|", 1)
                cursor_time = datetime.fromisoformat(cursor_time_raw)
                cursor_id = UUID(cursor_id_raw)
            except ValueError as exc:
                raise ValueError("Invalid event cursor") from exc

            statement = (
                select(EventModel)
                .where(
                    EventModel.project_id == project_id,
                    (
                        (EventModel.occurred_at > cursor_time)
                        | (
                            (EventModel.occurred_at == cursor_time)
                            & (EventModel.id > cursor_id)
                        )
                    ),
                )
                .order_by(EventModel.occurred_at.asc(), EventModel.id.asc())
                .limit(limit)
            )

        return list(await session.scalars(statement))


async def event_stream(
    project_id: UUID,
    *,
    cursor: str | None,
):
    current_cursor = cursor

    yield ": TITAN event stream connected\n\n"

    while True:
        try:
            events = await _get_events_after(project_id, current_cursor)
        except ValueError:
            yield "event: error\ndata: {"message":"Invalid event cursor"}\n\n"
            return

        if events:
            for event in events:
                current_cursor = _cursor_value(event)
                yield (
                    f"id: {current_cursor}\n"
                    "event: titan.event\n"
                    f"data: {_serialize_event(event)}\n\n"
                )
            continue

        await asyncio.sleep(1.0)
        yield ": keep-alive\n\n"


async def build_event_stream_response(
    project_id: UUID,
    *,
    cursor: str | None,
    operator: OperatorIdentity,
) -> StreamingResponse:
    async with SessionFactory() as session:
        project = await session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return StreamingResponse(
        event_stream(project_id, cursor=cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-TITAN-Operator": operator.subject,
        },
    )
