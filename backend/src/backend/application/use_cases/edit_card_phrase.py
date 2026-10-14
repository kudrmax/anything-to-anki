from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import CandidateNotFoundError, InvalidPhraseError

if TYPE_CHECKING:
    from backend.application.utils.rewrite_phrase import RewritePhrase
    from backend.domain.ports.candidate_repository import CandidateRepository


class EditCardPhraseUseCase:
    """Lets the user rewrite the card phrase by hand, in the slot AI polishing uses.

    The source phrase stays untouched, so the user can still see it and revert.
    Meaning and TTS are kept: a hand edit is a small tweak the user controls.
    A text without the target is refused (TargetNotInPhraseError).
    """

    def __init__(self, candidate_repo: CandidateRepository, rewrite_phrase: RewritePhrase) -> None:
        self._candidate_repo = candidate_repo
        self._rewrite_phrase = rewrite_phrase

    def execute(self, candidate_id: int, phrase: str) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None or candidate.id is None:
            raise CandidateNotFoundError(candidate_id)
        edited = phrase.strip()
        if not edited:
            raise InvalidPhraseError("Phrase cannot be empty")
        if edited == candidate.phrase.text:
            return
        self._rewrite_phrase.execute(candidate, edited)
