from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.recent_dtos import (
    RecentBoardDTO,
    RecentCollectionDTO,
    RecentSourceDTO,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from backend.application.dto.collection_dtos import CollectionNodeDTO
    from backend.application.use_cases.get_sources import GetSourcesUseCase
    from backend.application.use_cases.list_collections import ListCollectionsUseCase
    from backend.domain.ports.recent_use_repository import RecentUseRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.recent_use import RecentUse


class GetRecentUseCase:
    """Recent: the sources and collections the user worked with, the latest first. A source
    reads as in the lists, a collection as in the tree."""

    def __init__(
        self,
        recent_uses: RecentUseRepository,
        source_repo: SourceRepository,
        sources: GetSourcesUseCase,
        collections: ListCollectionsUseCase,
    ) -> None:
        self._recent_uses = recent_uses
        self._source_repo = source_repo
        self._sources = sources
        self._collections = collections

    def board(self, query: str = "") -> RecentBoardDTO:
        key = query.strip().casefold()
        uses = sorted(self._recent_uses.list_all(), key=_latest_first)
        nodes = {node.id: node for node in _walk(self._collections.execute().collections)}
        stored = {s.id: s for s in self._source_repo.list_all() if _matches(s.title, key)}
        used_sources = [
            stored[u.scope.source_id] for u in uses
            if u.scope.source_id is not None and u.scope.source_id in stored
        ]
        rows = {summary.id: summary for summary in self._sources.summaries(used_sources)}
        items: list[RecentSourceDTO | RecentCollectionDTO] = []
        for use in uses:
            source_id, collection_id = use.scope.source_id, use.scope.collection_id
            if source_id is not None and source_id in rows:
                items.append(RecentSourceDTO(used_at=use.used_at, source=rows[source_id]))
            elif collection_id is not None and collection_id in nodes:
                node = nodes[collection_id]
                if _matches(node.name, key):
                    items.append(RecentCollectionDTO(
                        used_at=use.used_at, collection=node, path=_path(nodes, node),
                    ))
        return RecentBoardDTO(items=items)


def _latest_first(use: RecentUse) -> tuple[float, str]:
    return -use.used_at.timestamp(), use.scope.token


def _matches(name: str | None, key: str) -> bool:
    return not key or key in (name or "").casefold()


def _walk(nodes: list[CollectionNodeDTO]) -> Iterator[CollectionNodeDTO]:
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _path(nodes: dict[int, CollectionNodeDTO], node: CollectionNodeDTO) -> list[str]:
    path: list[str] = []
    parent = nodes.get(node.parent_id) if node.parent_id is not None else None
    while parent is not None:
        path.insert(0, parent.name)
        parent = nodes.get(parent.parent_id) if parent.parent_id is not None else None
    return path
