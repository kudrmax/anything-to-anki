from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.document_dtos import (
    BlockDTO,
    DocumentPositionDTO,
    HighlightDTO,
    LineDTO,
    SourceDocumentDTO,
)
from backend.domain.exceptions import SourceHasNoDocumentError
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.value_objects.document import Heading, ListItem, Paragraph

if TYPE_CHECKING:
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.value_objects.document import Block, Line
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.shown_place import ShownPlace


class GetSourceDocumentUseCase:
    """The document of a source for its screen, with the targets of its cards — the shown
    phrases — to mark in it.

    Where marks would overlap, the one that starts first stays; of two starting together,
    the longer one (a phrasal verb rather than its verb).
    """

    def __init__(self, document_repo: DocumentRepository, card_query: CardQuery) -> None:
        self._document_repo = document_repo
        self._card_query = card_query

    def execute(self, source_id: int) -> SourceDocumentDTO:
        document = self._document_repo.get(source_id)
        if document is None:
            raise SourceHasNoDocumentError(source_id)
        layout = DocumentLayout(document)
        placed = sorted(
            (
                (_target_span(layout, place), place)
                for place in self._card_query.shown_places(source_id)
            ),
            key=lambda pair: (pair[0][0], -pair[0][1], pair[1].phrase_id),
        )
        highlights: list[HighlightDTO] = []
        taken_until = -1
        for (start, end), place in placed:
            if start < taken_until:
                continue
            highlights.append(_highlight(place, layout.position(start, end)))
            taken_until = end
        return SourceDocumentDTO(
            blocks=[_block(block) for block in document.blocks], highlights=highlights,
        )


def _target_span(layout: DocumentLayout, place: ShownPlace) -> tuple[int, int]:
    """Where the target of the source phrase stands in the document text, first word to last."""
    start, _ = layout.span(place.position)
    phrase = place.source_phrase
    words = [phrase.words[i] for i in phrase.target]
    return start + words[0].start, start + words[-1].end


def _highlight(place: ShownPlace, position: DocumentPosition) -> HighlightDTO:
    return HighlightDTO(
        phrase_id=place.phrase_id,
        word_id=place.word_id,
        position=DocumentPositionDTO.from_position(position),
        cefr_level=place.cefr_level,
        is_phrasal_verb=place.is_phrasal_verb,
    )


def _block(block: Block) -> BlockDTO:
    match block:
        case Heading():
            return BlockDTO(type="heading", lines=[LineDTO(text=block.text)], level=block.level)
        case Paragraph():
            return BlockDTO(
                type="paragraph", lines=_lines(block.lines), mode=block.mode.value,
            )
        case ListItem():
            return BlockDTO(
                type="list_item",
                lines=_lines(block.lines),
                ordered=block.ordered,
                depth=block.depth,
            )


def _lines(lines: tuple[Line, ...]) -> list[LineDTO]:
    return [LineDTO(text=line.text) for line in lines]
