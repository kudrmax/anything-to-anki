from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.exceptions import InvalidPhraseError, PhraseNotFoundError

if TYPE_CHECKING:
    from backend.application.utils.rewrite_phrase import RewritePhrase
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.ports.unit_of_work import UnitOfWork


class EditCardPhraseUseCase:
    """Lets the user rewrite the card phrase by hand, in the slot AI polishing uses.

    The source phrase stays untouched, so the user can still see it and revert.
    Meaning and TTS are kept: a hand edit is a small tweak the user controls.
    A text without the target is refused (TargetNotInPhraseError).
    """

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        rewrite_phrase: RewritePhrase,
        lock: SourceOperationLock,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._rewrite_phrase = rewrite_phrase
        self._lock = lock

    def execute(self, phrase_id: int, phrase: str) -> None:
        with self._unit_of_work.write():
            self._edit(phrase_id, phrase)

    def _edit(self, phrase_id: int, phrase: str) -> None:
        occ = self._occurrences.get(phrase_id)
        word = self._candidate_repo.get_by_id(occ.candidate_id) if occ is not None else None
        if occ is None or word is None:
            raise PhraseNotFoundError(phrase_id)
        ensure_source_free(self._lock, word.source_id)
        edited = phrase.strip()
        if not edited:
            raise InvalidPhraseError("Phrase cannot be empty")
        if edited == occ.phrase.text:
            return
        self._rewrite_phrase.of_phrase(occ, word, edited)
