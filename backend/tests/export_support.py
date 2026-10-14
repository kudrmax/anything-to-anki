"""Words to learn with the phrases of their decisions, for export tests without a database.

A phrase id is never its word's id (`PHRASE_ID_OFFSET`), so mixing the two fails a test.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.utils.export_queue import ExportCard
from backend.domain.entities.occurrence import Occurrence
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.word_status import WordStatus

PHRASE_ID_OFFSET = 1000


def phrase_id_of(word_id: int) -> int:
    """The id the decision phrase of the word gets in these tests."""
    return word_id + PHRASE_ID_OFFSET


def export_card(
    word: StoredCandidate,
    text: Phrase,
    *,
    meaning: CandidateMeaning | None = None,
    media: CandidateMedia | None = None,
    tts: CandidateTTS | None = None,
    cloze: CandidateCloze | None = None,
    kind: DecisionKind | None = None,
) -> ExportCard:
    """The word and the phrase of its decision. The decision is a cloze when the phrase has
    cloze markup, unless `kind` says otherwise."""
    assert word.id is not None
    if kind is None:
        kind = DecisionKind.CLOZE if cloze is not None else DecisionKind.LEARN
    return ExportCard(word=word, phrase=Occurrence(
        id=phrase_id_of(word.id),
        candidate_id=word.id,
        origin=OccurrenceOrigin.AUTO,
        source_phrase=text,
        phrase_position=None,
        key=None,
        fragment_score=None,
        shown_by=ShownBy.SELECTION,
        is_decision=True,
        decision_kind=kind,
        meaning=meaning,
        media=media,
        tts=tts,
        cloze=cloze,
    ))


class ExportCards:
    """The words and decision phrases the export queue reads: `words` stands for the
    candidate repository, the object itself for the occurrence repository."""

    def __init__(self) -> None:
        self._cards: list[ExportCard] = []
        self.words = MagicMock()
        self.words.get_by_source.side_effect = lambda source_id: [
            c.word for c in self._cards if c.word.source_id == source_id
        ]
        self.words.get_all_by_status.side_effect = self._with_status

    def put(self, cards: Iterable[ExportCard]) -> None:
        """These cards and no others."""
        self._cards = list(cards)

    def decision_phrases(self, candidate_ids: list[int]) -> dict[int, Occurrence]:
        return {c.word_id: c.phrase for c in self._cards if c.word_id in candidate_ids}

    def _with_status(self, status: WordStatus) -> list[StoredCandidate]:
        return sorted(
            (c.word for c in self._cards if c.word.status is status),
            key=lambda w: w.source_id,
        )


def with_phrase(card: ExportCard, **changes: object) -> ExportCard:
    """The card with its decision phrase changed."""
    return replace(card, phrase=replace(card.phrase, **changes))  # type: ignore[arg-type]


def with_word(card: ExportCard, **changes: object) -> ExportCard:
    """The card with its word changed."""
    return replace(card, word=replace(card.word, **changes))  # type: ignore[arg-type]
