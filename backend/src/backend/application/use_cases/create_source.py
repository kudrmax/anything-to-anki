from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.source import Source
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.source_type import SourceType

if TYPE_CHECKING:
    from backend.domain.ports.source_repository import SourceRepository


class CreateSourceUseCase:
    """Creates a new text source for processing."""

    def __init__(self, source_repo: SourceRepository) -> None:
        self._source_repo = source_repo

    def execute(
        self,
        raw_text: str,
        source_type: SourceType = SourceType.TEXT,
        title: str | None = None,
    ) -> Source:
        if not raw_text.strip():
            msg = "Source text cannot be empty"
            raise ValueError(msg)
        resolved_title = title.strip() if title and title.strip() else raw_text[:100]
        source = Source(
            raw_text=raw_text,
            status=SourceStatus.NEW,
            source_type=source_type,
            title=resolved_title,
        )
        return self._source_repo.create(source)
