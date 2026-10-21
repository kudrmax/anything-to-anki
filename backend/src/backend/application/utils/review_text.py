from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.document_dtos import (
    BlockDTO,
    ContentsEntryDTO,
    DocumentPositionDTO,
    HighlightDTO,
    LineDTO,
    ReviewContentsDTO,
    TextChunkDTO,
)
from backend.domain.exceptions import SourceHasNoDocumentError, SourceNotFoundError
from backend.domain.services.text_chunks import chunk_with
from backend.domain.services.text_marks import PlacedMark, marks_shown
from backend.domain.value_objects.document import Heading, ListItem, Paragraph
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from backend.application.utils.open_review import OpenReview
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.application.utils.source_texts import SourceText, SourceTexts
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.services.document_layout import DocumentLayout
    from backend.domain.value_objects.document import Block, Document, Line
    from backend.domain.value_objects.shown_place import ShownPlace


class ReviewText:
    """The text of an open review's set: its contents, and a chunk of a source's document
    with the targets of its cards — the shown phrases — to mark in it. A source's document is
    laid out once and kept in `texts`."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        document_repo: DocumentRepository,
        card_query: CardQuery,
        card_state_query: CardStateQuery,
        texts: SourceTexts,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._document_repo = document_repo
        self._card_query = card_query
        self._card_state_query = card_state_query
        self._texts = texts

    def contents(self, review: OpenReview) -> ReviewContentsDTO:
        """The sources of the review's set that have a document, in the set's order."""
        sources = [
            source
            for source in self._scope_resolver.reviewable_sources(
                SourceScope.parse(review.scope_token),
            )
            if source.id in review.source_ids
        ]
        hints = self._document_repo.size_hints([s.id for s in sources if s.id is not None])
        return ReviewContentsDTO(
            version=review.contents_version,
            documents=[
                ContentsEntryDTO(
                    source_id=source.id, title=source.title or "", size_hint=hints[source.id],
                )
                for source in sources
                if source.id is not None and source.id in hints
            ],
        )

    def chunk(self, review: OpenReview, source_id: int, block: int) -> TextChunkDTO:
        """The chunk of the source's document that holds the block; LAST_BLOCK names the
        last one. SourceNotFoundError when the source is not in the set,
        SourceHasNoDocumentError when it has no document, TextBlockNotFoundError when the
        document has no such block."""
        if source_id not in review.source_ids:
            raise SourceNotFoundError(source_id)
        text = self._text(source_id)
        chunk = chunk_with(text.chunks, block)
        blocks = range(chunk.first_block, chunk.end_block)
        places = self._card_query.shown_places(source_id, blocks)
        done = self._card_state_query.done_of_phrases([p.phrase_id for p in places])
        layout = text.layout
        return TextChunkDTO(
            source_id=source_id,
            first_block=chunk.first_block,
            end_block=chunk.end_block,
            block_count=len(text.bounds),
            start_offset=text.bounds[chunk.first_block][0],
            end_offset=text.bounds[chunk.end_block - 1][1],
            text_length=len(layout.text),
            blocks=[
                block_dto(layout.document.blocks[index], text.numbers[index])
                for index in blocks
            ],
            highlights=highlights(layout, places, done),
        )

    def _text(self, source_id: int) -> SourceText:
        fingerprint = self._document_repo.fingerprint(source_id)
        if fingerprint is None:
            raise SourceHasNoDocumentError(source_id)

        def read() -> Document:
            document = self._document_repo.get(source_id)
            if document is None:
                raise SourceHasNoDocumentError(source_id)
            return document

        return self._texts.of(source_id, fingerprint, read)


def highlights(
    layout: DocumentLayout, places: Iterable[ShownPlace], done: Mapping[int, bool],
) -> list[HighlightDTO]:
    """The targets of the places that don't overlap, in reading order. `done`: as the
    stored projection has the card; a card it has no live row of is open."""
    by_id = {place.phrase_id: place for place in places}
    marks = marks_shown(
        PlacedMark(place.phrase_id, *target_span(layout, place)) for place in by_id.values()
    )
    return [
        _highlight(by_id[mark.phrase_id], layout, mark, is_done=done.get(mark.phrase_id, False))
        for mark in marks
    ]


def target_span(layout: DocumentLayout, place: ShownPlace) -> tuple[int, int]:
    """Where the target of the source phrase stands in the document text, first word to last."""
    start, _ = layout.span(place.position)
    phrase = place.source_phrase
    words = [phrase.words[i] for i in phrase.target]
    return start + words[0].start, start + words[-1].end


def block_dto(block: Block, number: int | None) -> BlockDTO:
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
                number=number,
            )


def _highlight(
    place: ShownPlace, layout: DocumentLayout, mark: PlacedMark, *, is_done: bool,
) -> HighlightDTO:
    return HighlightDTO(
        phrase_id=place.phrase_id,
        word_id=place.word_id,
        position=DocumentPositionDTO.from_position(layout.position(mark.start, mark.end)),
        cefr_level=place.cefr_level,
        is_phrasal_verb=place.is_phrasal_verb,
        is_done=is_done,
    )


def _lines(lines: tuple[Line, ...]) -> list[LineDTO]:
    return [LineDTO(text=line.text) for line in lines]
