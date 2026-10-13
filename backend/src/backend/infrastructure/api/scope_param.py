from __future__ import annotations

from fastapi import HTTPException

from backend.domain.value_objects.source_scope import SourceScope


def parse_scope(raw: str) -> SourceScope:
    try:
        return SourceScope.parse(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
