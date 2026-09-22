import re
from datetime import UTC, datetime
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from titan.persistence.models import EvidenceModel, MemoryItemModel


@dataclass(frozen=True, slots=True)
class MemoryHit:
    id: UUID
    kind: str
    content: str
    importance: int
    score: float
    metadata: dict[str, Any]


class MemoryStore:
    async def remember(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID | None,
        kind: str,
        content: str,
        importance: int = 50,
        source_type: str = "SYSTEM",
        source_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryItemModel:
        if not 0 <= importance <= 100:
            raise ValueError("Memory importance must be between 0 and 100")
        if not content.strip():
            raise ValueError("Memory content cannot be empty")

        item = MemoryItemModel(
            id=uuid4(),
            project_id=project_id,
            task_id=task_id,
            kind=kind,
            content=content.strip(),
            importance=importance,
            source_type=source_type,
            source_id=source_id,
            metadata_json=metadata or {},
            expires_at=expires_at,
        )
        session.add(item)
        await session.flush()
        return item

    async def search(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        query: str = "",
        task_id: UUID | None = None,
        limit: int = 20,
    ) -> list[MemoryHit]:
        if limit < 1 or limit > 100:
            raise ValueError("Memory search limit must be between 1 and 100")

        statement = (
            select(MemoryItemModel)
            .where(
                MemoryItemModel.project_id == project_id,
                (MemoryItemModel.expires_at.is_(None))
                | (MemoryItemModel.expires_at > datetime.now(UTC)),
            )
            .order_by(MemoryItemModel.importance.desc(), MemoryItemModel.created_at.desc())
            .limit(200)
        )
        if task_id is not None:
            statement = statement.where(
                (MemoryItemModel.task_id == task_id) | (MemoryItemModel.task_id.is_(None))
            )

        rows = list((await session.scalars(statement)).all())
        terms = _terms(query)
        hits: list[MemoryHit] = []

        for row in rows:
            haystack = f"{row.kind} {row.content} {row.metadata_json}".lower()
            matches = sum(term in haystack for term in terms)
            if terms and matches == 0:
                continue

            lexical = matches / len(terms) if terms else 0.0
            score = lexical * 0.7 + (row.importance / 100) * 0.3
            hits.append(
                MemoryHit(
                    id=row.id,
                    kind=row.kind,
                    content=row.content,
                    importance=row.importance,
                    score=score,
                    metadata=row.metadata_json,
                )
            )

        hits.sort(key=lambda item: (item.score, item.importance), reverse=True)
        return hits[:limit]

    async def remember_evidence(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        task_id: UUID | None,
        evidence_type: str,
        title: str,
        content: str,
        source_uri: str | None = None,
        source_ref: str | None = None,
        confidence: float = 0.5,
        checksum: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceModel:
        if not 0 <= confidence <= 1:
            raise ValueError("Evidence confidence must be between 0 and 1")
        if not title.strip() or not content.strip():
            raise ValueError("Evidence title and content cannot be empty")

        evidence = EvidenceModel(
            id=uuid4(),
            project_id=project_id,
            task_id=task_id,
            evidence_type=evidence_type,
            title=title.strip(),
            content=content.strip(),
            source_uri=source_uri,
            source_ref=source_ref,
            confidence=confidence,
            checksum=checksum,
            metadata_json=metadata or {},
        )
        session.add(evidence)
        await session.flush()
        return evidence


def _terms(query: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    return tuple(dict.fromkeys(term for term in normalized.split() if len(term) >= 2))
