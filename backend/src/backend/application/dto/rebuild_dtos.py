from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.domain.services.source_operations import busy_caption
from backend.domain.value_objects.rebuild_mode import RebuildMode  # noqa: TC001
from backend.domain.value_objects.source_operation_kind import SourceOperationKind  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.services.rebuild_plan import RebuildPlan


class RebuildCountsDTO(BaseModel):
    """What a rebuild changes, as the user is told.

    `cards_lost_generation`: removed cards that had something made for them;
    `cards_moved`: cards that move to a phrase with nothing made for it yet;
    `cards_recut`: cards cut again; `cards_recut_lost_text_generation`: those of them that
    lose their polish, audio or video; `cards_became_ready` and `cards_left_ready`: cards
    moving into Ready or out of it; `nothing_to_update`: the rebuild would change nothing.
    """

    words_added: int
    words_removed: int
    cards_lost_generation: int
    cards_moved: int
    cards_recut: int
    cards_recut_lost_text_generation: int
    cards_became_ready: int
    cards_left_ready: int
    nothing_to_update: bool

    @staticmethod
    def of(plan: RebuildPlan) -> RebuildCountsDTO:
        counts = plan.counts
        return RebuildCountsDTO(
            words_added=counts.words_added,
            words_removed=counts.words_removed,
            cards_lost_generation=counts.cards_lost_generation,
            cards_moved=counts.cards_moved,
            cards_recut=counts.cards_recut,
            cards_recut_lost_text_generation=counts.cards_recut_lost_text_generation,
            cards_became_ready=counts.cards_became_ready,
            cards_left_ready=counts.cards_left_ready,
            nothing_to_update=plan.is_empty,
        )

    @staticmethod
    def total(counts: Sequence[RebuildCountsDTO]) -> RebuildCountsDTO:
        """The counts of several sources as one: nothing to update only if none has any."""
        return RebuildCountsDTO(
            words_added=sum(c.words_added for c in counts),
            words_removed=sum(c.words_removed for c in counts),
            cards_lost_generation=sum(c.cards_lost_generation for c in counts),
            cards_moved=sum(c.cards_moved for c in counts),
            cards_recut=sum(c.cards_recut for c in counts),
            cards_recut_lost_text_generation=sum(
                c.cards_recut_lost_text_generation for c in counts
            ),
            cards_became_ready=sum(c.cards_became_ready for c in counts),
            cards_left_ready=sum(c.cards_left_ready for c in counts),
            nothing_to_update=all(c.nothing_to_update for c in counts),
        )


class SetOutcomeDTO(BaseModel):
    """How the sources of a set went: `skipped` were held by another operation at their
    turn, `failed` ran into an error. A single source that ran has none of either."""

    skipped: int = 0
    failed: int = 0


class RebuildPreviewDTO(SetOutcomeDTO):
    """A rebuild as it would go in `mode`."""

    mode: RebuildMode
    counts: RebuildCountsDTO

    @staticmethod
    def total(
        mode: RebuildMode, previews: Sequence[RebuildPreviewDTO], outcome: SetOutcomeDTO,
    ) -> RebuildPreviewDTO:
        return RebuildPreviewDTO(
            mode=mode,
            counts=RebuildCountsDTO.total([p.counts for p in previews]),
            skipped=outcome.skipped,
            failed=outcome.failed,
        )


class RebuildSummaryDTO(SetOutcomeDTO):
    """What a rebuild in `mode` changed."""

    mode: RebuildMode
    counts: RebuildCountsDTO

    @staticmethod
    def total(
        mode: RebuildMode, summaries: Sequence[RebuildSummaryDTO], outcome: SetOutcomeDTO,
    ) -> RebuildSummaryDTO:
        return RebuildSummaryDTO(
            mode=mode,
            counts=RebuildCountsDTO.total([s.counts for s in summaries]),
            skipped=outcome.skipped,
            failed=outcome.failed,
        )


class TopicRefreshSummaryDTO(SetOutcomeDTO):
    """What refreshing a topic added."""

    words_added: int
    phrases_added: int

    @staticmethod
    def total(
        refreshes: Sequence[TopicRefreshSummaryDTO], outcome: SetOutcomeDTO,
    ) -> TopicRefreshSummaryDTO:
        return TopicRefreshSummaryDTO(
            words_added=sum(r.words_added for r in refreshes),
            phrases_added=sum(r.phrases_added for r in refreshes),
            skipped=outcome.skipped,
            failed=outcome.failed,
        )


class OperationState(StrEnum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class SourceOperationDTO(BaseModel):
    """The last long operation started on a set of sources, and its result once done."""

    operation_id: int
    kind: SourceOperationKind
    state: OperationState
    # What the user is told while it runs.
    caption: str = ""
    preview: RebuildPreviewDTO | None = None
    summary: RebuildSummaryDTO | None = None
    refresh: TopicRefreshSummaryDTO | None = None
    error: str | None = None

    @staticmethod
    def running(operation_id: int, kind: SourceOperationKind) -> SourceOperationDTO:
        return SourceOperationDTO(
            operation_id=operation_id, kind=kind, state=OperationState.RUNNING,
            caption=busy_caption(kind),
        )
