from __future__ import annotations

from pydantic import BaseModel

from backend.domain.value_objects.document_position import DocumentPosition


class DocumentPositionDTO(BaseModel):
    """A piece of one block of a source's document; characters in code points, end exclusive."""

    block: int
    start_line: int
    start_char: int
    end_line: int
    end_char: int

    @staticmethod
    def from_position(position: DocumentPosition) -> DocumentPositionDTO:
        return DocumentPositionDTO(
            block=position.block,
            start_line=position.start_line,
            start_char=position.start_char,
            end_line=position.end_line,
            end_char=position.end_char,
        )

    def to_position(self) -> DocumentPosition:
        return DocumentPosition(
            block=self.block,
            start_line=self.start_line,
            start_char=self.start_char,
            end_line=self.end_line,
            end_char=self.end_char,
        )


class LineDTO(BaseModel):
    text: str


class BlockDTO(BaseModel):
    """A heading, a paragraph (`flow` — sentences run across lines, `lines` — each line apart)
    or a list item. A heading has one line."""

    type: str  # 'heading' | 'paragraph' | 'list_item'
    lines: list[LineDTO]
    level: int | None = None
    mode: str | None = None
    ordered: bool | None = None
    depth: int | None = None
    # A list item's number among the items around it; an unordered one shows a bullet.
    number: int | None = None


class HighlightDTO(BaseModel):
    """A target of a card to mark on the source screen."""

    phrase_id: int
    word_id: int
    position: DocumentPositionDTO
    cefr_level: str | None
    is_phrasal_verb: bool
    # The card is done: its word is decided, or its phrase skipped.
    is_done: bool


class TextChunkDTO(BaseModel):
    """Blocks `first_block` up to `end_block` of a source's document, with the targets to
    mark in them. The offsets, in the document's text, and the counts only size the
    placeholders of the text not loaded."""

    source_id: int
    first_block: int
    end_block: int
    block_count: int
    start_offset: int
    end_offset: int
    text_length: int
    blocks: list[BlockDTO]
    # Targets that don't overlap, in reading order
    highlights: list[HighlightDTO]


class ContentsEntryDTO(BaseModel):
    """A source of a review set that has a document; `size_hint` only sizes its placeholder."""

    source_id: int
    title: str
    size_hint: int


class ReviewContentsDTO(BaseModel):
    """The documents of an open review's set in the set's order; `version` moves on when
    the set's sources change."""

    version: int
    documents: list[ContentsEntryDTO]


class ChunkHighlightsDTO(BaseModel):
    """The targets to mark in a chunk of a source's text the client was sent, as they are
    now: they replace the chunk's marks."""

    source_id: int
    first_block: int
    highlights: list[HighlightDTO]


class TextChunkRef(BaseModel):
    """A chunk of a source's text the client holds: the source and the chunk's first
    block."""

    source_id: int
    first_block: int
