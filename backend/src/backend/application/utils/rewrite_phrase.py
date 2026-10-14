from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.utils.phrase_reader import PhraseReader
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.value_objects.phrase import Phrase


class RewritePhrase:
    """The one way a card gets a new text for its phrase — from AI, by hand, or any other.

    The target is found in the new text by the card's dictionary form, so the text may
    change its forms ("scattered" → "scatters"). Without the target the text is refused
    with TargetNotInPhraseError and the card keeps its phrase.
    """

    def __init__(self, candidate_repo: CandidateRepository, phrase_reader: PhraseReader) -> None:
        self._candidate_repo = candidate_repo
        self._phrase_reader = phrase_reader

    def execute(self, candidate: StoredCandidate, text: str) -> Phrase:
        assert candidate.id is not None
        phrase = self._phrase_reader.read_for(text, candidate.lemma)
        self._candidate_repo.set_polished_phrase(candidate.id, phrase)
        return phrase
