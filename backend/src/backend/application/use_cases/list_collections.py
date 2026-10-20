from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.collection_dtos import (
    CollectionNodeDTO,
    CollectionTreeDTO,
    ScopeCountsDTO,
)
from backend.application.dto.source_dtos import ProgressDTO
from backend.domain.services.collection_tree import CollectionTree
from backend.domain.services.source_actions import (
    can_export,
    can_review,
    progress_caption,
    review_fraction,
)
from backend.domain.services.source_operations import operations_offer
from backend.domain.services.source_review_status import (
    IS_REVIEWED,
    derive_review_status,
    stored_status_of_set,
)
from backend.domain.services.source_stage import is_pending, set_operation, shown_status
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from backend.application.utils.review_progress import ReviewProgress
    from backend.application.utils.topic_generation import TopicGenerationProbe
    from backend.domain.entities.collection import Collection
    from backend.domain.entities.source import Source
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.collection_repository import CollectionRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository


class ListCollectionsUseCase:
    """The collection tree in manual order, each node counting its whole subtree and
    reading as a set of sources under review: the same status, progress and caption a
    source has, from the same functions."""

    def __init__(
        self,
        collection_repo: CollectionRepository,
        source_repo: SourceRepository,
        review_progress: ReviewProgress,
        generation_probe: TopicGenerationProbe,
        lock: SourceOperationLock,
        card_query: CardQuery,
    ) -> None:
        self._lock = lock
        self._card_query = card_query
        self._collection_repo = collection_repo
        self._source_repo = source_repo
        self._review_progress = review_progress
        self._generation_probe = generation_probe

    def execute(self) -> CollectionTreeDTO:
        tree = CollectionTree(self._collection_repo.list_all())
        sources = self._source_repo.list_all()
        busy = self._lock.operations()
        busy_kinds = {source_id: held.kind for source_id, held in busy.items()}
        pending = {
            s.id for s in sources
            if is_pending(
                s.status,
                awaiting_generation=self._generation_probe.of(s).awaiting,
                busy=s.id in busy,
            )
        }
        ids = [s.id for s in sources if s.id is not None]
        cards = self._review_progress.cards(ids)
        progress = self._review_progress.progress_of(cards)
        learn_counts = self._card_query.learn_counts(ids)
        reviewed = {
            s.id for s in sources
            if s.id is not None
            and IS_REVIEWED[derive_review_status(
                s.status, progress.get(s.id, DecisionProgress()),
            )]
        }

        def counts(scope: SourceScope, selected: list[Source]) -> ScopeCountsDTO:
            selected_ids = [s.id for s in selected if s.id is not None]
            decisions = sum(
                (progress.get(i, DecisionProgress()) for i in selected_ids), DecisionProgress(),
            )
            status = derive_review_status(
                stored_status_of_set(s.status for s in selected), decisions,
            )
            operation = set_operation(
                status, (busy[i].kind for i in selected_ids if i in busy),
            )
            pending_count = sum(1 for i in selected_ids if i in pending)
            learn_count = sum(learn_counts.get(i, 0) for i in selected_ids)
            offer = operations_offer(selected, busy_kinds)
            return ScopeCountsDTO(
                total=len(selected),
                reviewed=sum(1 for i in selected_ids if i in reviewed),
                pending=pending_count,
                progress=ProgressDTO.of(decisions),
                status=shown_status(status, operation),
                can_process=pending_count > 0,
                can_review=can_review(scope, status),
                review_fraction=review_fraction(status, decisions),
                progress_caption=progress_caption(
                    status,
                    sum(len(cards.get(i, [])) for i in selected_ids),
                    decisions,
                    learn_count,
                    operation,
                ),
                available_operations=list(offer.operations),
                can_start_operation=offer.can_start,
                operation_hint=offer.hint,
                can_export=can_export(status, learn_count),
            )

        def node(collection: Collection) -> CollectionNodeDTO:
            assert collection.id is not None
            subtree = tree.subtree_ids(collection.id)
            return CollectionNodeDTO(
                id=collection.id,
                name=collection.name,
                parent_id=collection.parent_id,
                counts=counts(
                    SourceScope.collection(collection.id),
                    [s for s in sources if s.collection_id in subtree],
                ),
                depth=tree.depth(collection.id),
                accepts_collections=tree.can_hold_children(collection.id),
                move_targets=tree.move_targets(collection.id),
                children=[node(child) for child in tree.children(collection.id)],
            )

        return CollectionTreeDTO(
            all=counts(SourceScope.all(), sources),
            unsorted=counts(
                SourceScope.unsorted(), [s for s in sources if s.collection_id is None],
            ),
            max_depth=tree.max_depth,
            collections=[node(c) for c in tree.children(None)],
        )
