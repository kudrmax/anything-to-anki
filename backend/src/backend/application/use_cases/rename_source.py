from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceNotFoundError

if TYPE_CHECKING:
    from backend.domain.ports.source_repository import SourceRepository


class RenameSourceUseCase:
    """Renames an existing source."""

    def __init__(self, source_repo: SourceRepository) -> None:
        self._source_repo = source_repo

    def execute(self, source_id: int, title: str) -> None:
        if not title.strip():
            msg = "Title cannot be empty"
            raise ValueError(msg)
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        self._source_repo.update_title(source_id, title.strip())
