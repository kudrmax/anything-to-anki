from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.entities.word_decision import WordDecision
from backend.domain.exceptions import PhraseNotFoundError
from backend.domain.services.card_decision import decide
from backend.domain.value_objects.word_status import WordStatus

if TYPE_CHECKING:
    from backend.application.utils.decided_elsewhere import DecidedElsewhere
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.occurrence import Occurrence
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.word_decision_repository import WordDecisionRepository
    from backend.domain.services.card_decision import DecisionAction, DecisionOutcome

DECIDED = frozenset({WordStatus.LEARN, WordStatus.KNOWN})


@dataclass(frozen=True)
class _KnownMark:
    """What a Known decision changed in the user's lists, to take back when it is left:
    it added the lemma to Known (`added`), taking it out of Unknown (`was_unknown`)."""

    added: bool = False
    was_unknown: bool = False


_NO_MARK = _KnownMark()


class DecidePhraseUseCase:
    """Learn, Cloze, Known, Skip, Unskip or undo on a card (a phrase of a word).

    The rules are `card_decision.decide`. Besides the word and the phrase, a decision keeps
    the known words in sync, remembers known/learn verdicts for calibration and refreshes
    the review status.
    """

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        vocabulary: UserVocabulary,
        decision_repo: WordDecisionRepository,
        review_status: ReviewStatusUpdater,
        cloze_repo: CandidateClozeRepository,
        decided_elsewhere: DecidedElsewhere,
        lock: SourceOperationLock,
    ) -> None:
        self._lock = lock
        self._occurrences = occurrence_repo
        self._candidates = candidate_repo
        self._vocabulary = vocabulary
        self._decision_repo = decision_repo
        self._review_status = review_status
        self._cloze_repo = cloze_repo
        self._decided_elsewhere = decided_elsewhere

    def execute(self, occurrence_id: int, action: DecisionAction) -> None:
        occ = self._occurrences.get(occurrence_id)
        if occ is None:
            raise PhraseNotFoundError(occurrence_id)
        word = self._candidates.get_by_id(occ.candidate_id)
        if word is None:
            raise PhraseNotFoundError(occurrence_id)
        ensure_source_free(self._lock, word.source_id)
        before = word.status
        elsewhere = (
            self._decided_elsewhere.of(word.lemma) if before is WordStatus.PENDING else None
        )
        outcome = decide(occ, before, action, elsewhere)
        mark = self._known_mark(word, before, outcome.word_status)
        self._write(occ, before, outcome, mark)
        self._follow(word, before, outcome.word_status, mark)

    def _known_mark(
        self, word: StoredCandidate, before: WordStatus, after: WordStatus,
    ) -> _KnownMark:
        """What the word's Known changes: nothing when the user knew the lemma before this
        decision (another source, the settings)."""
        if after is not WordStatus.KNOWN:
            return _NO_MARK
        if before is WordStatus.KNOWN:
            return _KnownMark(word.known_added, word.was_unknown)
        vocabulary = self._vocabulary.snapshot()
        if vocabulary.is_known(word.lemma):
            return _NO_MARK
        return _KnownMark(added=True, was_unknown=vocabulary.is_unknown(word.lemma))

    def _write(
        self, occ: Occurrence, before: WordStatus, outcome: DecisionOutcome, mark: _KnownMark,
    ) -> None:
        assert occ.id is not None
        if outcome.word_status is not before:
            self._candidates.set_word_status(
                occ.candidate_id, outcome.word_status,
                known_added=mark.added, was_unknown=mark.was_unknown,
            )
        if (outcome.is_decision, outcome.decision_kind) != (occ.is_decision, occ.decision_kind):
            self._occurrences.set_decision(
                occ.candidate_id, occ.id if outcome.is_decision else None, outcome.decision_kind,
            )
        if outcome.skipped != occ.skipped:
            self._occurrences.set_skipped(occ.id, outcome.skipped)
        if outcome.drop_cloze and occ.cloze is not None:
            self._cloze_repo.delete_by_phrase_id(occ.id)

    def _follow(
        self, word: StoredCandidate, before: WordStatus, after: WordStatus, mark: _KnownMark,
    ) -> None:
        """The review status changes with any action; knowledge (known or learning) only with
        the word's status, and then in every source showing the lemma."""
        if after is before:
            self._review_status.refresh(word.source_id)
            return
        if mark.added:
            self._vocabulary.mark_known(word.lemma, word.pos)
        elif before is WordStatus.KNOWN and word.known_added:
            self._vocabulary.forget_known(word.lemma, word.pos)
            if word.was_unknown:
                self._vocabulary.restore_unknown(word.lemma)
        if after is WordStatus.LEARN:
            self._vocabulary.start_learning(word.lemma)
        self._remember_decision(word, before, after)
        self._review_status.refresh(word.source_id)
        self._review_status.refresh_showing({word.lemma.lower()})

    def _remember_decision(
        self, word: StoredCandidate, before: WordStatus, after: WordStatus,
    ) -> None:
        """Only single words: a phrase's frequency is not comparable with a word's."""
        if word.is_phrasal_verb or " " in word.lemma:
            return
        if after in DECIDED:
            self._decision_repo.record(WordDecision(
                lemma=word.lemma,
                zipf_frequency=word.zipf_frequency,
                is_known=after is WordStatus.KNOWN,
            ))
        elif before in DECIDED:
            self._decision_repo.forget(word.lemma)
