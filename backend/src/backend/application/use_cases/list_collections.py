from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import (
    CollectionNodeDTO,
    CollectionTreeDTO,
    ScopeCountsDTO,
)
from backend.domain.services.collection_tree import CollectionTree
from backend.domain.services.source_stage import is_pending
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.application.utils.topic_generation import TopicGenerationProbe
    from backend.domain.entities.collection import Collection
    from backend.domain.entities.source import Source
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.source_repository import SourceRepository


class ListCollectionsUseCase:
    """The collection tree in manual order, each node counting its whole subtree."""

    def __init__(
        self,
        collection_repo: CollectionRepository,
        source_repo: SourceRepository,
        generation_probe: TopicGenerationProbe,
    ) -> None:
        self._collection_repo = collection_repo
        self._source_repo = source_repo
        self._generation_probe = generation_probe

    def execute(self) -> CollectionTreeDTO:
        tree = CollectionTree(self._collection_repo.list_all())
        sources = self._source_repo.list_all()
        pending = {
            s.id for s in sources
            if is_pending(s.status, awaiting_generation=self._generation_probe.of(s).awaiting)
        }

        def counts(selected: list[Source]) -> ScopeCountsDTO:
            return ScopeCountsDTO(
                total=len(selected),
                reviewed=sum(1 for s in selected if s.status is SourceStatus.REVIEWED),
                pending=sum(1 for s in selected if s.id in pending),
            )

        def node(collection: Collection) -> CollectionNodeDTO:
            assert collection.id is not None
            subtree = tree.subtree_ids(collection.id)
            return CollectionNodeDTO(
                id=collection.id,
                name=collection.name,
                parent_id=collection.parent_id,
                counts=counts([s for s in sources if s.collection_id in subtree]),
                depth=tree.depth(collection.id),
                accepts_collections=tree.can_hold_children(collection.id),
                move_targets=tree.move_targets(collection.id),
                children=[node(child) for child in tree.children(collection.id)],
            )

        return CollectionTreeDTO(
            all=counts(sources),
            unsorted=counts([s for s in sources if s.collection_id is None]),
            max_depth=tree.max_depth,
            collections=[node(c) for c in tree.children(None)],
        )
