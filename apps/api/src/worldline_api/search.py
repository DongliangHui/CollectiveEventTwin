from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Case, Evidence, Signal


@dataclass(frozen=True)
class SearchResult:
    object_type: str
    object_id: str
    case_id: str
    title: str
    summary: str
    score: float


class SearchAdapter(Protocol):
    def search(self, session: Session, query: str, limit: int = 20) -> list[SearchResult]:
        ...


class PostgresFtsSearchAdapter:
    """P0 database search adapter.

    The SQLAlchemy implementation uses portable predicates for local tests.
    The interface is intentionally isolated so production Postgres FTS or
    OpenSearch can replace it without changing route or domain code.
    """

    def search(self, session: Session, query: str, limit: int = 20) -> list[SearchResult]:
        normalized = query.strip()
        if not normalized:
            return []

        pattern = f"%{normalized}%"
        results: list[SearchResult] = []
        results.extend(
            SearchResult("case", item.id, item.id, item.title, item.payload.get("boundary", ""), 0.9)
            for item in session.scalars(
                select(Case).where(or_(Case.title.ilike(pattern), Case.slug.ilike(pattern))).limit(limit)
            )
        )
        remaining = max(0, limit - len(results))
        if remaining:
            results.extend(
                SearchResult("signal", item.id, item.case_id, item.title, item.summary, 0.75)
                for item in session.scalars(
                    select(Signal).where(or_(Signal.title.ilike(pattern), Signal.summary.ilike(pattern))).limit(remaining)
                )
            )
        remaining = max(0, limit - len(results))
        if remaining:
            results.extend(
                SearchResult("evidence", item.id, item.case_id, item.title, item.masked_excerpt, 0.65)
                for item in session.scalars(
                    select(Evidence).where(or_(Evidence.title.ilike(pattern), Evidence.masked_excerpt.ilike(pattern))).limit(remaining)
                )
            )
        return results


search_adapter: SearchAdapter = PostgresFtsSearchAdapter()
