from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.source_dtos import (
    ProgressDTO,
    SourceBoardDTO,
    SourceDTO,
    SourceGroupDTO,
)
from backend.domain.services.source_actions import (
    can_delete,
    can_export,
    can_review,
    progress_caption,
    review_fraction,
)
from backend.domain.services.source_operations import operations_offer
from backend.domain.services.source_review_status import derive_review_status
from backend.domain.services.source_stage import is_pending, shown_status, source_stage
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_stage import SourceStage

if TYPE_CHECKING:
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


class GetSourcesUseCase:
    """Retrieves sources for the lists: they read cards light — shown phrases and the
    facts of their words — for all their sources at once."""

    def __init__(
        self,
        source_repo: SourceRepository,
        scope_resolver: SourceScopeResolver,
        generation_probe: TopicGenerationProbe,
        review_progress: ReviewProgress,
        card_query: CardQuery,
        lock: SourceOperationLock,
    ) -> None:
        self._source_repo = source_repo
        self._scope_resolver = scope_resolver
        self._generation_probe = generation_probe
        self._review_progress = review_progress
        self._card_query = card_query
        self._lock = lock

    def list_all(self) -> list[SourceDTO]:
        return self._summaries(self._source_repo.list_all())

    def board(self, scope: SourceScope, query: str = "") -> SourceBoardDTO:
        """The scope's sources in the user's order, split into its groups. The stages the
        summaries read decide the groups, so the cards are read once."""
        key = query.strip().casefold()
        sources = [s for s in self._scope_resolver.members(scope) if _matches(s, key)]
        summaries = {summary.id: summary for summary in self._summaries(sources)}
        groups = self._scope_resolver.arrange(
            sources, {i: SourceStage(summary.stage) for i, summary in summaries.items()},
        )
        return SourceBoardDTO(
            title=self._scope_resolver.title(scope),
            groups=[
                SourceGroupDTO(
                    stage=group.stage.value if group.stage is not None else None,
                    sources=[summaries[s.id] for s in group.sources if s.id is not None],
                )
                for group in groups
            ],
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
        offer = operations_offer(
            [source], {source.id: busy_with} if busy_with is not None else {},
        )
        status = derive_review_status(source.status, progress)
        return SourceDTO(
            id=source.id,
            title=source.title or "",
            status=shown_status(status, busy_with),
            stage=source_stage(
                source.status, progress, awaiting_generation=generation.awaiting,
            ).value,
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
            available_operations=list(offer.operations),
            can_start_operation=offer.can_start,
            busy_with=busy_with,
            operation_hint=offer.hint,
            can_process=is_pending(
                source.status,
                awaiting_generation=generation.awaiting,
                busy=busy_with is not None,
            ),
            can_review=can_review(SourceScope.source(source.id), status),
            can_export=can_export(status, learn_count),
            can_delete=can_delete(source, busy_with),
            review_fraction=review_fraction(status, progress),
            progress_caption=progress_caption(
                status, len(cards), progress, learn_count, busy_with,
            ),
        )


def _matches(source: Source, key: str) -> bool:
    return not key or key in (source.title or "").casefold()


def _stage(operation: HeldOperation | None) -> str | None:
    if operation is None or operation.stage is None:
        return None
    return operation.stage.value
