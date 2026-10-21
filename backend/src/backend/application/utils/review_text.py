from __future__ import annotations

import bisect
from typing import TYPE_CHECKING

from backend.application.dto.document_dtos import (
    BlockDTO,
    ChunkHighlightsDTO,
    ContentsEntryDTO,
    DocumentPositionDTO,
    HighlightDTO,
    LineDTO,
    ReviewContentsDTO,
    TextChunkDTO,
)
from backend.domain.exceptions import (
    SourceHasNoDocumentError,
    SourceNotFoundError,
    TextBlockNotFoundError,
)
from backend.domain.services.text_chunks import chunk_with
from backend.domain.services.text_marks import PlacedMark, marks_shown
from backend.domain.value_objects.document import Heading, ListItem, Paragraph
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from backend.application.dto.document_dtos import TextChunkRef
    from backend.application.utils.open_review import OpenReview
    from backend.application.utils.served_text import ChunkRef
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.application.utils.source_texts import SourceText, SourceTexts
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.services.document_layout import DocumentLayout
    from backend.domain.services.text_chunks import TextChunk
    from backend.domain.value_objects.card_state_rows import CardStateRow
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
        last one. The review counts it as served. SourceNotFoundError when the source is
        not in the set, SourceHasNoDocumentError when it has no document,
        TextBlockNotFoundError when the document has no such block."""
        if source_id not in review.source_ids:
            raise SourceNotFoundError(source_id)
        text = self._text(source_id)
        chunk = chunk_with(text.chunks, block)
        blocks = range(chunk.first_block, chunk.end_block)
        places = self._card_query.shown_places(source_id, blocks)
        review.text.serve(source_id, chunk, places)
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
            highlights=self._highlights(layout, places),
        )

    def changed_highlights(
        self,
        review: OpenReview,
        live: Mapping[int, CardStateRow],
        removed: Mapping[int, int],
        source_order: Sequence[int],
    ) -> list[ChunkHighlightsDTO]:
        """The marks of the served chunks whose marks the changed cards changed — `live`:
        the changed cards as they are now; `removed`: the gone ones, each with its source —
        in the order of `source_order`, then by first block. Each is served again. Reads a
        source's document only for a chunk whose marks changed."""
        served = review.text.sources()
        changed = {p: row.source_id for p, row in live.items() if row.source_id in served}
        changed |= {p: s for p, s in removed.items() if s in served}
        if not changed:
            return []
        blocks = self._card_query.phrase_blocks(changed)
        placed: list[tuple[int, int]] = []
        anywhere: set[int] = set()
        for phrase_id, source_id in changed.items():
            found = blocks.get(phrase_id)
            if found is None:
                anywhere.add(source_id)
            elif found.block is not None:
                placed.append((source_id, found.block))
        now: dict[ChunkRef, list[ShownPlace]] = {}
        for source_id, chunks in review.text.candidates(placed, anywhere).items():
            now |= _by_chunk(
                source_id, chunks,
                self._card_query.shown_places_in(
                    source_id, [range(c.first_block, c.end_block) for c in chunks],
                ),
            )
        touched = review.text.touched(now)
        rank = {source_id: at for at, source_id in enumerate(source_order)}
        layouts = {
            source_id: self._text(source_id).layout for source_id in {s for s, _ in touched}
        }
        answer: list[ChunkHighlightsDTO] = []
        for source_id, first in sorted(touched, key=lambda ref: (rank.get(ref[0], -1), ref[1])):
            chunk = review.text.chunk_of(source_id, first)
            assert chunk is not None
            places = now[source_id, first]
            review.text.serve(source_id, chunk, places)
            answer.append(ChunkHighlightsDTO(
                source_id=source_id, first_block=first,
                highlights=self._highlights(layouts[source_id], places),
            ))
        return answer

    def register(
        self, review: OpenReview, refs: Sequence[TextChunkRef],
    ) -> list[ChunkHighlightsDTO]:
        """The chunks a client of a review opened again holds from before: each one of a
        source of the set that has a document, which a chunk of it starts at, is served,
        with its marks, in the order asked; any other is left out. One read of places per
        source."""
        texts: dict[int, SourceText | None] = {}
        held: dict[ChunkRef, TextChunk] = {}
        for ref in refs:
            if ref.source_id not in review.source_ids:
                continue
            if ref.source_id not in texts:
                try:
                    texts[ref.source_id] = self._text(ref.source_id)
                except SourceHasNoDocumentError:
                    texts[ref.source_id] = None
            text = texts[ref.source_id]
            if text is None:
                continue
            try:
                chunk = chunk_with(text.chunks, ref.first_block)
            except TextBlockNotFoundError:
                continue
            if chunk.first_block == ref.first_block:
                held[ref.source_id, chunk.first_block] = chunk
        places: dict[ChunkRef, list[ShownPlace]] = {}
        for source_id in dict.fromkeys(s for s, _ in held):
            chunks = sorted(
                (c for (s, _), c in held.items() if s == source_id), key=lambda c: c.first_block,
            )
            places |= _by_chunk(
                source_id, chunks,
                self._card_query.shown_places_in(
                    source_id, [range(c.first_block, c.end_block) for c in chunks],
                ),
            )
        answer: list[ChunkHighlightsDTO] = []
        for (source_id, first), chunk in held.items():
            text = texts[source_id]
            assert text is not None
            review.text.serve(source_id, chunk, places[source_id, first])
            answer.append(ChunkHighlightsDTO(
                source_id=source_id, first_block=first,
                highlights=self._highlights(text.layout, places[source_id, first]),
            ))
        return answer

    def _highlights(
        self, layout: DocumentLayout, places: Sequence[ShownPlace],
    ) -> list[HighlightDTO]:
        done = self._card_state_query.done_of_phrases([p.phrase_id for p in places])
        return highlights(layout, places, done)

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


def _by_chunk(
    source_id: int, chunks: Sequence[TextChunk], places: Iterable[ShownPlace],
) -> dict[ChunkRef, list[ShownPlace]]:
    """The places of each chunk, which are in order: a place is in its block's chunk."""
    found: dict[ChunkRef, list[ShownPlace]] = {(source_id, c.first_block): [] for c in chunks}
    firsts = [c.first_block for c in chunks]
    for place in places:
        first = firsts[bisect.bisect_right(firsts, place.position.block) - 1]
        found[source_id, first].append(place)
    return found


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
