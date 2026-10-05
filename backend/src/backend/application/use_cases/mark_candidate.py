from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.word_decision import WordDecision
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus

if TYPE_CHECKING:
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.known_word_repository import KnownWordRepository
    from backend.domain.ports.word_decision_repository import WordDecisionRepository

DECISION_STATUSES = frozenset({CandidateStatus.KNOWN, CandidateStatus.LEARN})


class MarkCandidateUseCase:
    """Marks a candidate status (or undoes it back to pending), keeps known
    words in sync and remembers known/learn verdicts for calibration.

    Any status change drops the cloze markup: the user decided on the card anew. A card
    already exported keeps it: Anki holds it as a cloze note."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        known_word_repo: KnownWordRepository,
        decision_repo: WordDecisionRepository,
        review_status: ReviewStatusUpdater,
        cloze_repo: CandidateClozeRepository,
        anki_sync_repo: AnkiSyncRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._known_word_repo = known_word_repo
        self._decision_repo = decision_repo
        self._review_status = review_status
        self._cloze_repo = cloze_repo
        self._anki_sync_repo = anki_sync_repo

    def execute(self, candidate_id: int, status: CandidateStatus) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        self.apply(candidate, status)
        if candidate_id not in self._anki_sync_repo.get_synced_candidate_ids([candidate_id]):
            self._cloze_repo.delete_by_candidate_id(candidate_id)

    def apply(self, candidate: StoredCandidate, status: CandidateStatus) -> None:
        """Sets the status with all its side effects, leaving the cloze markup as is."""
        assert candidate.id is not None
        self._candidate_repo.update_status(candidate.id, status)
        if status == CandidateStatus.KNOWN:
            self._known_word_repo.add(candidate.lemma, candidate.pos)
        elif candidate.status == CandidateStatus.KNOWN:
            self._known_word_repo.remove_by_lemma(candidate.lemma, candidate.pos)
        self._remember_decision(candidate, status)
        self._review_status.refresh(candidate.source_id)

    def _remember_decision(self, candidate: StoredCandidate, status: CandidateStatus) -> None:
        """Only single words: a phrase's frequency is not comparable with a word's."""
        if candidate.is_phrasal_verb or " " in candidate.lemma:
            return
        if status in DECISION_STATUSES:
            self._decision_repo.record(WordDecision(
                lemma=candidate.lemma,
                zipf_frequency=candidate.zipf_frequency,
                is_known=status == CandidateStatus.KNOWN,
            ))
        elif candidate.status in DECISION_STATUSES:
            self._decision_repo.forget(candidate.lemma)
