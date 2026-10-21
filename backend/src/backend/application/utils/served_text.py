from __future__ import annotations

import bisect
import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from backend.domain.services.text_chunks import TextChunk
    from backend.domain.value_objects.shown_place import ShownPlace

# The size of the digest of a chunk's places: two chunks with different places have the
# same digest with a chance of 2^-128.
PLACES_DIGEST_BYTES = 16

type ChunkRef = tuple[int, int]
"""A chunk of a source's text: the source's id and the chunk's first block."""


@dataclass(frozen=True, slots=True)
class PlaceKey:
    """What the mark of a shown phrase in the text is made of: its place, where its target
    words stand in the phrase, its CEFR level and whether it is a phrasal verb. Equal keys
    of every phrase in a chunk give the chunk equal marks; whether a card is done is not
    part of it."""

    block: int
    position: tuple[int, int, int, int, int]
    target: tuple[tuple[int, int], ...]
    cefr_level: str | None
    is_phrasal_verb: bool

    @staticmethod
    def of(place: ShownPlace) -> PlaceKey:
        position = place.position
        words = place.source_phrase.words
        return PlaceKey(
            block=position.block,
            position=(
                position.block, position.start_line, position.start_char,
                position.end_line, position.end_char,
            ),
            target=tuple((words[i].start, words[i].end) for i in place.source_phrase.target),
            cefr_level=place.cefr_level,
            is_phrasal_verb=place.is_phrasal_verb,
        )


def places_digest(places: Iterable[ShownPlace]) -> bytes:
    """A digest of the phrases a chunk holds, each with its key, overlapped ones too."""
    keyed = sorted(
        ((place.phrase_id, PlaceKey.of(place)) for place in places), key=lambda pair: pair[0],
    )
    return hashlib.blake2b(repr(keyed).encode(), digest_size=PLACES_DIGEST_BYTES).digest()


@dataclass(frozen=True, slots=True)
class _Served:
    chunk: TextChunk
    digest: bytes


class ServedText:
    """The chunks of text an open review served, per source, each with a digest of the
    phrases it held when served — not where each phrase stands: a phrase's block comes from
    the store when a card changes."""

    def __init__(self) -> None:
        self._served: dict[int, dict[int, _Served]] = {}
        self._firsts: dict[int, list[int]] = {}

    def serve(self, source_id: int, chunk: TextChunk, places: Iterable[ShownPlace]) -> None:
        """The chunk was sent with these places: what was held for it is replaced."""
        served = self._served.setdefault(source_id, {})
        if chunk.first_block not in served:
            bisect.insort(self._firsts.setdefault(source_id, []), chunk.first_block)
        served[chunk.first_block] = _Served(chunk, places_digest(places))

    def sources(self) -> frozenset[int]:
        return frozenset(self._served)

    def chunk_of(self, source_id: int, block: int) -> TextChunk | None:
        """The served chunk of the source that holds the block."""
        firsts = self._firsts.get(source_id)
        if not firsts:
            return None
        index = bisect.bisect_right(firsts, block) - 1
        if index < 0:
            return None
        chunk = self._served[source_id][firsts[index]].chunk
        return chunk if block < chunk.end_block else None

    def candidates(
        self, placed: Iterable[tuple[int, int]], anywhere: Iterable[int],
    ) -> dict[int, list[TextChunk]]:
        """Source id → its served chunks, by first block, a changed card may have marks in:
        `placed` gives the source and block of each card with a block, and `anywhere` the
        sources of the cards whose block is not known any more — any chunk of these."""
        found: dict[int, dict[int, TextChunk]] = {}
        for source_id in anywhere:
            if source_id in self._served:
                found[source_id] = {f: s.chunk for f, s in self._served[source_id].items()}
        for source_id, block in placed:
            chunk = self.chunk_of(source_id, block)
            if chunk is not None:
                found.setdefault(source_id, {})[chunk.first_block] = chunk
        return {
            source_id: [chunks[first] for first in sorted(chunks)]
            for source_id, chunks in found.items()
        }

    def touched(self, now: Mapping[ChunkRef, Sequence[ShownPlace]]) -> set[ChunkRef]:
        """Of these served chunks, each with every place it holds now, those whose places
        differ from what was served."""
        return {
            (source_id, first)
            for (source_id, first), places in now.items()
            if (served := self._served.get(source_id, {}).get(first)) is not None
            and served.digest != places_digest(places)
        }

    def forget_source(self, source_id: int) -> None:
        self._served.pop(source_id, None)
        self._firsts.pop(source_id, None)

    def refs(self) -> list[ChunkRef]:
        return [
            (source_id, first)
            for source_id in sorted(self._firsts)
            for first in self._firsts[source_id]
        ]
