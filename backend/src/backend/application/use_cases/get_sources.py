from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import INITIALLY_SHOWN_CANDIDATES
from backend.application.dto.source_dtos import (
    ProgressDTO,
    SourceBoardDTO,
    SourceDetailDTO,
    SourceDTO,
    SourceGroupDTO,
)
from backend.domain.exceptions import SourceNotFoundError
from backend.domain.services.source_actions import (
    can_delete,
    can_export,
    can_review,
    progress_caption,
    review_fraction,
)
from backend.domain.services.source_operations import available_operation, operation_hint
from backend.domain.services.source_stage import shown_status, stage_of
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.source_stage import STAGE_ORDER

if TYPE_CHECKING:
    from backend.application.utils.card_views import CardViews
    from backend.application.utils.review_progress import ReviewProgress
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.application.utils.topic_generation import TopicGenerationProbe
    from backend.domain.entities.source import Source
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.services.collection_tree import CollectionTree
    from backend.domain.value_objects.held_operation import HeldOperation
    from backend.domain.value_objects.review_card import CardRow
    from backend.domain.value_objects.source_scope import SourceScope


class GetSourcesUseCase:
    """Retrieves sources (list and detail views).

    The lists read cards light — shown phrases and the facts of their words — for all
    their sources at once; only the detail view loads what was made for the cards.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        scope_resolver: SourceScopeResolver,
        generation_probe: TopicGenerationProbe,
        review_progress: ReviewProgress,
        card_query: CardQuery,
        card_views: CardViews,
        lock: SourceOperationLock,
    ) -> None:
        self._source_repo = source_repo
        self._scope_resolver = scope_resolver
        self._generation_probe = generation_probe
        self._review_progress = review_progress
        self._card_query = card_query
        self._card_views = card_views
        self._lock = lock

    def list_all(self) -> list[SourceDTO]:
        return self._summaries(self._source_repo.list_all())

    def board(self, scope: SourceScope, query: str = "") -> SourceBoardDTO:
        key = query.strip().casefold()
        sources = [
            s for s in self._scope_resolver.sources(scope)
            if not key or key in (s.title or "").casefold()
        ]
        summaries = self._summaries(sources)
        groups = [
            SourceGroupDTO(stage=stage.value, sources=[s for s in summaries if s.stage == stage])
            for stage in STAGE_ORDER
        ]
        return SourceBoardDTO(
            title=self._scope_resolver.title(scope),
            groups=[g for g in groups if g.sources],
        )

    def _summaries(self, sources: list[Source]) -> list[SourceDTO]:
        tree = self._scope_resolver.tree()
        ids = [s.id for s in sources if s.id is not None]
        cards = self._review_progress.cards(ids)
        progress = self._review_progress.progress_of(cards)
        learn_counts = self._card_query.learn_counts(ids)
        operations = self._lock.operations()
        return [
            self._summary(
                s, tree, cards.get(s.id, []), progress.get(s.id, DecisionProgress()),
                learn_counts.get(s.id, 0), operations.get(s.id),
            )
            for s in sources if s.id is not None
        ]

    def _summary(
        self,
        source: Source,
        tree: CollectionTree,
        cards: list[CardRow],
        progress: DecisionProgress,
        learn_count: int,
        operation: HeldOperation | None,
    ) -> SourceDTO:
        assert source.id is not None
        generation = self._generation_probe.of(source)
        collection_id = source.collection_id
        collection_path = (
            tree.path(collection_id)
            if collection_id is not None and tree.has(collection_id)
            else []
        )
        busy_with = operation.kind if operation is not None else None
        return SourceDTO(
            id=source.id,
            title=source.title or "",
            status=shown_status(source.status, busy_with),
            stage=stage_of(source.status, awaiting_generation=generation.awaiting).value,
            kind=source.kind.value if source.kind else None,
            role=source.role.value,
            has_video=source.has_video,
            source_url=source.source_url,
            video_downloaded=source.video_path is not None,
            created_at=source.created_at,
            candidate_count=len(cards),
            learn_count=learn_count,
            progress=ProgressDTO.of(progress),
            processing_stage=_stage(operation),
            collection_id=collection_id,
            collection_path=collection_path,
            awaiting_generation=generation.awaiting,
            generation_status=generation.status,
            generation_error=generation.error,
            is_permanent=source.is_permanent,
            available_operation=available_operation(source),
            can_start_operation=busy_with is None,
            busy_with=busy_with,
            operation_hint=operation_hint(busy_with),
            can_review=can_review(source.status),
            can_export=can_export(source.status),
            can_delete=can_delete(source, busy_with),
            review_fraction=review_fraction(source.status, progress),
            progress_caption=progress_caption(
                source.status, len(cards), progress, learn_count, busy_with,
            ),
        )

    def get_by_id(
        self,
        source_id: int,
        sort_order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> SourceDetailDTO:
        source = self._source_repo.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(source_id)
        assert source.id is not None
        listing = self._card_views.listed(source.id, sort_order)
        initially_shown = (
            None if sort_order == CandidateSortOrder.CHRONOLOGICAL
            else INITIALLY_SHOWN_CANDIDATES
        )
        operation = self._lock.operations().get(source.id)
        busy_with = operation.kind if operation is not None else None
        return SourceDetailDTO(
            id=source.id,
            title=source.title or "",
            status=shown_status(source.status, busy_with),
            kind=source.kind.value if source.kind else None,
            role=source.role.value,
            has_video=source.has_video,
            can_polish_phrases=source.can_polish_phrases,
            has_source_text=source.has_text,
            source_url=source.source_url,
            video_downloaded=source.video_path is not None,
            error_message=source.error_message,
            processing_stage=_stage(operation),
            busy_with=busy_with,
            learn_count=self._card_query.learn_counts([source.id]).get(source.id, 0),
            created_at=source.created_at,
            candidates=listing.cards,
            progress=ProgressDTO.of(listing.progress),
            initially_shown_candidates=initially_shown,
        )


def _stage(operation: HeldOperation | None) -> str | None:
    if operation is None or operation.stage is None:
        return None
    return operation.stage.value
