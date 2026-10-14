from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.card_decision import word_status_of
from backend.domain.value_objects.review_card import ReviewCard
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from backend.application.utils.decided_elsewhere import DecidedElsewhere
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository


class ReviewCards:
    """The cards of the review list — shown phrases with their words — with everything
    made for them, and whether a word open here is done via another source."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        decided_elsewhere: DecidedElsewhere,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrence_repo = occurrence_repo
        self._decided_elsewhere = decided_elsewhere

    def of_source(self, source_id: int) -> list[ReviewCard]:
        words = {w.id: w for w in self._candidate_repo.get_by_source(source_id)}
        shown = self._occurrence_repo.shown_by_word(source_id)
        statuses = {word_id: word_status_of(word) for word_id, word in words.items()}
        elsewhere = self._decided_elsewhere.of_lemmas(
            word.lemma for word_id, word in words.items()
            if statuses[word_id] is WordStatus.PENDING
        )
        return [
            ReviewCard(
                word=words[word_id],
                occurrence=occurrence,
                word_status=statuses[word_id],
                elsewhere=elsewhere.get(words[word_id].lemma),
            )
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

    def card(self, word: StoredCandidate, occurrence: Occurrence) -> ReviewCard:
        status = word_status_of(word)
        return ReviewCard(
            word=word,
            occurrence=occurrence,
            word_status=status,
            elsewhere=(
                self._decided_elsewhere.of(word.lemma) if status is WordStatus.PENDING else None
            ),
        )
