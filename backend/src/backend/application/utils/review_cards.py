from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.card_view import open_elsewhere
from backend.domain.value_objects.review_card import CardContext, ReviewCard

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.word_state_repository import WordStateRepository
    from backend.domain.value_objects.card_choice import WordState


class ReviewCards:
    """The cards of the review list — shown phrases with their words — with everything
    made for them, whether a word open here is done via another source, and what the card
    view is derived from: all of it from the request's one snapshot of what the user knows."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        word_states: WordStateRepository,
        vocabulary: UserVocabulary,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo
        self._word_states = word_states
        self._vocabulary = vocabulary

    def of_sources(self, source_ids: Sequence[int]) -> list[ReviewCard]:
        """The cards of the sources, source by source in the order given."""
        return [card for source_id in source_ids for card in self._of_source(source_id)]

    def _of_source(self, source_id: int) -> list[ReviewCard]:
        words = {w.id: w for w in self._candidate_repo.get_by_source(source_id)}
        shown = self._occurrence_repo.shown_by_word(source_id)
        states = self._word_states.of_source(source_id)
        return [
            _card(words[word_id], occurrence, self._context(states[word_id]))
            for word_id, occurrences in shown.items() if word_id in words
            for occurrence in occurrences
        ]

    def of_phrase(self, phrase_id: int) -> ReviewCard | None:
        """The card of the phrase, whether or not it is shown now."""
        occurrence = self._occurrence_repo.get(phrase_id)
        if occurrence is None:
            return None
        word = self._candidate_repo.get_by_id(occurrence.candidate_id)
        if word is None:
            return None
        return self.card(word, occurrence)

    def of_phrases(self, phrase_ids: Sequence[int]) -> list[ReviewCard]:
        """The cards of these phrases in the order given, whether or not they are shown now;
        a phrase that is gone is left out. Read in one batch per kind of fact."""
        occurrences = {o.id: o for o in self._occurrence_repo.of_ids(phrase_ids)}
        word_ids = list(dict.fromkeys(o.candidate_id for o in occurrences.values()))
        words = {w.id: w for w in self._candidate_repo.get_by_ids(word_ids)}
        states = self._word_states.of_words(word_ids)
        cards: list[ReviewCard] = []
        for phrase_id in phrase_ids:
            occurrence = occurrences.get(phrase_id)
            if occurrence is None or occurrence.candidate_id not in words:
                continue
            word = words[occurrence.candidate_id]
            cards.append(_card(word, occurrence, self._context(states[occurrence.candidate_id])))
        return cards

    def card(self, word: StoredCandidate, occurrence: Occurrence) -> ReviewCard:
        assert word.id is not None
        state = self._word_states.of_word(word.id)
        assert state is not None
        return _card(word, occurrence, self._context(state))

    def _context(self, word: WordState) -> CardContext:
        return CardContext(
            word=word,
            knowledge=self._vocabulary.of(word.lemma),
            now=self._vocabulary.scope.now,
        )


def _card(word: StoredCandidate, occurrence: Occurrence, context: CardContext) -> ReviewCard:
    return ReviewCard(
        word=word, occurrence=occurrence,
        elsewhere=open_elsewhere(context.word, context.knowledge), context=context,
    )
