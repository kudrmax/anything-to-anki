from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.domain.services.source_operations import busy_caption
from backend.domain.value_objects.source_operation_kind import SourceOperationKind  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.services.rebuild_plan import RebuildPlan


class RebuildRequest(BaseModel):
    """`include_open`: the selection may also move off cards with generation, and phrases
    whose text changed lose their generation."""

    include_open: bool = False


class RebuildCountsDTO(BaseModel):
    """What a rebuild changes, as the user is told.

    `cards_new_phrase`: cards that get a phrase with nothing generated yet;
    `cards_text_reset`: cards whose text changed and whose generation is reset;
    `cards_without_generation`: shown cards with nothing generated after the rebuild;
    `nothing_to_update`: the rebuild would change nothing.
    """

    words_added: int
    words_removed: int
    cards_new_phrase: int
    cards_text_reset: int
    cards_without_generation: int
    nothing_to_update: bool

    @staticmethod
    def of(plan: RebuildPlan) -> RebuildCountsDTO:
        counts = plan.counts
        return RebuildCountsDTO(
            words_added=counts.words_added,
            words_removed=counts.words_removed,
            cards_new_phrase=counts.cards_new_phrase,
            cards_text_reset=counts.cards_text_reset,
            cards_without_generation=counts.cards_without_generation,
            nothing_to_update=plan.is_empty,
        )

    @staticmethod
    def total(counts: Sequence[RebuildCountsDTO]) -> RebuildCountsDTO:
        """The counts of several sources as one: nothing to update only if none has any."""
        return RebuildCountsDTO(
            words_added=sum(c.words_added for c in counts),
            words_removed=sum(c.words_removed for c in counts),
            cards_new_phrase=sum(c.cards_new_phrase for c in counts),
            cards_text_reset=sum(c.cards_text_reset for c in counts),
            cards_without_generation=sum(c.cards_without_generation for c in counts),
            nothing_to_update=all(c.nothing_to_update for c in counts),
        )


class SetOutcomeDTO(BaseModel):
    """How the sources of a set went: `skipped` were held by another operation at their
    turn, `failed` ran into an error. A single source that ran has none of either."""

    skipped: int = 0
    failed: int = 0


class RebuildPreviewDTO(SetOutcomeDTO):
    """A rebuild as it would go, without and with «Also unreviewed cards»; a source without
    text of its own has no such switch, so no `with_open`."""

    without_open: RebuildCountsDTO
    with_open: RebuildCountsDTO | None

    @staticmethod
    def total(
        previews: Sequence[RebuildPreviewDTO], outcome: SetOutcomeDTO,
    ) -> RebuildPreviewDTO:
        """The switch is there if any source has it; a source without it counts the same
        either way."""
        has_switch = any(p.with_open is not None for p in previews)
        return RebuildPreviewDTO(
            without_open=RebuildCountsDTO.total([p.without_open for p in previews]),
            with_open=RebuildCountsDTO.total(
                [p.with_open or p.without_open for p in previews],
            ) if has_switch else None,
            skipped=outcome.skipped,
            failed=outcome.failed,
        )


class RebuildSummaryDTO(SetOutcomeDTO):
    """What a rebuild changed."""

    include_open: bool
    counts: RebuildCountsDTO

    @staticmethod
    def total(
        summaries: Sequence[RebuildSummaryDTO], outcome: SetOutcomeDTO,
    ) -> RebuildSummaryDTO:
        return RebuildSummaryDTO(
            include_open=any(s.include_open for s in summaries),
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
