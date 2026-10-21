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


class HighlightDTO(BaseModel):
    """A target of a card to mark on the source screen."""

    phrase_id: int
    word_id: int
    position: DocumentPositionDTO
    cefr_level: str | None
    is_phrasal_verb: bool
    # The card is done: its word is decided, or its phrase skipped.
    is_done: bool


class SourceDocumentDTO(BaseModel):
    """The text of one source of a review set, with the targets to mark in it."""

    source_id: int
    title: str
    blocks: list[BlockDTO]
    # Targets that don't overlap, in reading order
    highlights: list[HighlightDTO]
