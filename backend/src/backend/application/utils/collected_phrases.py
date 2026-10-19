from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.entities.occurrence import Occurrence
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.utils.section_stamper import SectionStamper
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.value_objects.new_card import NewCard


@dataclass(frozen=True)
class CollectedPhrase:
    phrase_id: int
    new_word: bool    # the word was made for this phrase


class CollectedPhrases:
    """Stores phrases collected for a source that has no text of its own — a topic, the
    saved phrases. Each becomes a shown phrase of its word; the word is made when the source
    has none yet."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        stamper: SectionStamper,
    ) -> None:
        self._candidates = candidate_repo
        self._occurrences = occurrence_repo
        self._stamper = stamper

    def add(self, source_id: int, cards: Sequence[NewCard]) -> list[CollectedPhrase]:
        """The stored phrases, in the order of `cards`."""
        words = {w.key: w.id for w in self._occurrences.word_rows(source_id)}
        rule = self._stamper.rule()
        collected: list[CollectedPhrase] = []
        for card in cards:
            key = WordKey.of(card.word.lemma, card.word.is_phrasal_verb)
            word_id = words.get(key)
            new_word = word_id is None
            if word_id is None:
                word_id = self._candidates.add_word(card.word)
                words[key] = word_id
            added = self._occurrences.add(Occurrence(
                candidate_id=word_id,
                origin=OccurrenceOrigin.COLLECTED,
                source_phrase=card.phrase,
                phrase_position=card.position,
                key=None,
                fragment_score=None,
                earned_section=rule.earned(card.phrase, card.word),
                shown_by=ShownBy.USER,
                collected_from=card.origin,
            ))
            assert added.id is not None
            collected.append(CollectedPhrase(added.id, new_word))
        return collected
