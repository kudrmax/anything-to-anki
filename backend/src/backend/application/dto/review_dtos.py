from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from backend.application.constants import TEXT_CHUNKS_HELD_MAX
from backend.application.dto.document_dtos import (  # noqa: TC001 — pydantic field types
    ChunkHighlightsDTO,
    TextChunkDTO,
    TextChunkRef,
)
from backend.application.dto.source_dtos import (  # noqa: TC001 — pydantic field types
    CardDTO,
    ProgressDTO,
)
from backend.domain.value_objects.candidate_section import (
    CandidateSection,  # noqa: TC001 — pydantic field type
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder


class ReviewHeaderDTO(BaseModel):
    """What the review screen of a set of sources shows above its cards, for the whole set."""

    # The set's token, as the scope query parameter takes it back.
    scope: str
    title: str
    status: str
    progress: ProgressDTO
    learn_count: int  # words to learn
    # Some source of the set is held by an operation: its cards wait for it.
    busy: bool
    # A shown card's meaning failed because the AI is not available from here.
    ai_unavailable: bool


class OpenReviewRequest(BaseModel):
    """A review to open: the set, its order, the card asked for and the sections the client
    had open (a review opened again keeps them)."""

    scope: str
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE
    requested_id: int | None = None
    open_sections: list[CandidateSection] = Field(default_factory=list)
    # The chunks of text the client holds from before: the answer brings their marks.
    text_chunks: list[TextChunkRef] = Field(
        default_factory=list, max_length=TEXT_CHUNKS_HELD_MAX,
    )


class SectionOpenRequest(BaseModel):
    """A section of an open review opened or folded."""

    open: bool


@dataclass(frozen=True)
class ReviewContext:
    """What every request on an open review says: its id, the revision the client has seen
    and the card it shows now."""

    review_id: str
    since: int
    current: int | None


class ReviewRowDTO(BaseModel):
    """A row of the visible list at `index`: a card, or the row of a section that folds."""

    index: int
    kind: Literal["card", "section"]
    phrase_id: int | None = None
    position: int | None = None
    section: CandidateSection | None = None
    count: int | None = None
    open: bool | None = None


class ReviewLayoutDTO(BaseModel):
    """Rows of the visible list. `replace`: these are every row the client was sent,
    indexed anew, and the client drops the others; else they add to what it has."""

    version: int
    total_rows: int
    total_cards: int
    replace: bool
    rows: list[ReviewRowDTO]


class ReviewUpdateDTO(BaseModel):
    """The one answer of an open review: what changed for the client since `since`, up to
    `revision`."""

    review_id: str
    revision: int
    header: ReviewHeaderDTO
    layout: ReviewLayoutDTO | None = None
    # Full cards of the rows sent, new or changed since `since`.
    cards: list[CardDTO] = Field(default_factory=list)
    removed: list[int] = Field(default_factory=list)
    # Whether each card of the set whose row changed since `since` is done.
    done: dict[int, bool] = Field(default_factory=dict)
    focus_id: int | None = None
    # A chunk of a source's text, when the request asked for one.
    text: TextChunkDTO | None = None
    # The marks, as they are now, of the chunks of text the client was sent whose marks
    # changed.
    highlights: list[ChunkHighlightsDTO] = Field(default_factory=list)
    # The version of the set's contents: it moves on when the set's sources change.
    contents_version: int = 0
