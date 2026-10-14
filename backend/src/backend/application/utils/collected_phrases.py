from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.occurrence import Occurrence
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.value_objects.new_card import NewCard


class CollectedPhrases:
    """Stores phrases collected for a source that has no text of its own — a topic, the
    saved phrases. Each becomes a shown phrase of its word; the word is made when the source
    has none yet."""

    def __init__(
        self, candidate_repo: CandidateRepository, occurrence_repo: OccurrenceRepository,
    ) -> None:
        self._candidates = candidate_repo
        self._occurrences = occurrence_repo

    def add(self, source_id: int, cards: Sequence[NewCard], *, learn: bool = False) -> list[int]:
        """The ids of the stored phrases, in the order of `cards`. `learn`: a word made here
        is learned, its phrase being the phrase of the decision."""
        words = {w.key: w.id for w in self._occurrences.word_rows(source_id)}
        phrase_ids: list[int] = []
        for card in cards:
            key = WordKey.of(card.word.lemma, card.word.is_phrasal_verb)
            word_id = words.get(key)
            decided = word_id is None and learn
            if word_id is None:
                word_id = self._candidates.add_word(card.word)
                words[key] = word_id
            if decided:
                self._candidates.set_word_status(word_id, WordStatus.LEARN)
            added = self._occurrences.add(Occurrence(
                candidate_id=word_id,
                origin=OccurrenceOrigin.COLLECTED,
                source_phrase=card.phrase,
                phrase_position=card.position,
                key=None,
                fragment_score=None,
                shown_by=ShownBy.USER,
                is_decision=decided,
                decision_kind=DecisionKind.LEARN if decided else None,
                collected_from=card.origin,
            ))
            assert added.id is not None
            phrase_ids.append(added.id)
        return phrase_ids
