from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.domain.services.source_operations import busy_caption
from backend.domain.value_objects.source_operation_kind import SourceOperationKind  # noqa: TC001

if TYPE_CHECKING:
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


class RebuildPreviewDTO(BaseModel):
    """A rebuild as it would go, without and with «Also unreviewed cards»."""

    without_open: RebuildCountsDTO
    with_open: RebuildCountsDTO


class RebuildSummaryDTO(BaseModel):
    """What a rebuild changed."""

    include_open: bool
    counts: RebuildCountsDTO


class TopicRefreshSummaryDTO(BaseModel):
    """What refreshing a topic added, and how many untouched generated examples real
    phrases replaced."""

    words_added: int
    phrases_added: int
    phrases_replaced: int = 0


class OperationState(StrEnum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class SourceOperationDTO(BaseModel):
    """The last long operation started on a source, and its result once done."""

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
