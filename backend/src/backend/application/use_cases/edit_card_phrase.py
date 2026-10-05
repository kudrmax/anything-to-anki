from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import CandidateNotFoundError, InvalidPhraseError

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository


class EditCardPhraseUseCase:
    """Lets the user rewrite the card phrase by hand, in the slot AI polishing uses.

    The source phrase stays untouched, so the user can still see it and revert.
    Meaning and TTS are kept: a hand edit is a small tweak the user controls.
    """

    def __init__(self, candidate_repo: CandidateRepository) -> None:
        self._candidate_repo = candidate_repo

    def execute(self, candidate_id: int, phrase: str) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None or candidate.id is None:
            raise CandidateNotFoundError(candidate_id)
        edited = phrase.strip()
        if not edited:
            raise InvalidPhraseError("Phrase cannot be empty")
        if edited == candidate.card_phrase:
            return
        self._candidate_repo.set_polished_fragment(candidate.id, edited)
        if candidate.polish_reverted:
            self._candidate_repo.set_polish_reverted(candidate.id, False)
