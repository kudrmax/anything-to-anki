from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
    from backend.domain.ports.candidate_tts_repository import CandidateTTSRepository


class PhraseEnrichmentReset:
    """Drops what was made for the old card phrase once the card shows another one.

    Meaning explains the word in the old phrase and TTS speaks the old phrase,
    so both have to be generated again.
    """

    def __init__(
        self, meaning_repo: CandidateMeaningRepository, tts_repo: CandidateTTSRepository,
    ) -> None:
        self._meaning_repo = meaning_repo
        self._tts_repo = tts_repo

    def reset(self, candidate_id: int) -> None:
        self._meaning_repo.delete_by_candidate_id(candidate_id)
        self._tts_repo.delete_by_candidate_id(candidate_id)
