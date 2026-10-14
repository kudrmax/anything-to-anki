from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.domain.exceptions import SourceNotFoundError
from backend.domain.ports.source_repository import SourceRepository

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from backend.domain.entities.source import Source
    from backend.domain.value_objects.source_role import SourceRole
    from backend.domain.value_objects.source_status import SourceStatus


class InMemorySourceRepository(SourceRepository):
    """Port fake for the parts of SourceRepository the collection use cases touch."""

    def __init__(self, sources: Sequence[Source]) -> None:
        self.items: dict[int, Source] = {s.id: s for s in sources if s.id is not None}

    def list_all(self) -> list[Source]:
        return sorted(self.items.values(), key=lambda s: s.created_at, reverse=True)

    def get_by_id(self, source_id: int) -> Source | None:
        return self.items.get(source_id)

    def set_collections(self, placements: Mapping[int, int | None]) -> None:
        for source_id, collection_id in placements.items():
            if source_id not in self.items:
                raise SourceNotFoundError(source_id)
            self.items[source_id] = replace(self.items[source_id], collection_id=collection_id)

    def create(self, source: Source) -> Source:
        raise NotImplementedError

    def get_first_by_role(self, role: SourceRole) -> Source | None:
        raise NotImplementedError

    def update_status(
        self,
        source_id: int,
        status: SourceStatus,
        *,
        error_message: str | None = None,
    ) -> None:
        raise NotImplementedError

    def update_title(self, source_id: int, title: str) -> None:
        raise NotImplementedError

    def update_video_path(self, source_id: int, video_path: str | None) -> None:
        raise NotImplementedError

    def delete(self, source_id: int) -> None:
        raise NotImplementedError

    def get_title_map(self, source_ids: list[int]) -> dict[int, str]:
        raise NotImplementedError
