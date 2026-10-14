"""Words with the phrase of their decision, for export tests that seed repository mocks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.value_objects.document_position import DocumentPosition
    from backend.domain.value_objects.phrase import Phrase


@dataclass
class ExportWord(StoredCandidate):
    """A word as the code under test sees it, carrying the phrase of its decision and what
    was made for that phrase, for `decision_of`."""

    source_phrase: Phrase | None = None
    polished_phrase: Phrase | None = None
    polish_reverted: bool = False
    phrase_position: DocumentPosition | None = None
    meaning: CandidateMeaning | None = None
    media: CandidateMedia | None = None
    tts: CandidateTTS | None = None
    cloze: CandidateCloze | None = None


def decision_of(candidate: StoredCandidate) -> Occurrence:
    """The phrase of the word's decision; a word with cloze markup was decided as a cloze.
    The phrase id is the word id."""
    assert isinstance(candidate, ExportWord)
    assert candidate.id is not None
    assert candidate.source_phrase is not None
    return Occurrence(
        id=candidate.id,
        candidate_id=candidate.id,
        origin=OccurrenceOrigin.AUTO,
        source_phrase=candidate.source_phrase,
        phrase_position=candidate.phrase_position,
        key=None,
        fragment_score=None,
        shown_by=ShownBy.SELECTION,
        is_decision=True,
        decision_kind=DecisionKind.CLOZE if candidate.cloze is not None else DecisionKind.LEARN,
        polished_phrase=candidate.polished_phrase,
        polish_reverted=candidate.polish_reverted,
        meaning=candidate.meaning,
        media=candidate.media,
        tts=candidate.tts,
        cloze=candidate.cloze,
    )


class DecisionsOf:
    """An occurrence repository answering only `decision_phrases`, from the words a
    candidate-repository mock was told to return."""

    def __init__(self, candidate_repo: MagicMock) -> None:
        self._candidate_repo = candidate_repo

    def decision_phrases(self, candidate_ids: list[int]) -> dict[int, Occurrence]:
        words: list[StoredCandidate] = []
        for method in (self._candidate_repo.get_by_source, self._candidate_repo.get_all_by_status):
            if isinstance(method.return_value, list):
                words.extend(method.return_value)
        return {w.id: decision_of(w) for w in words if w.id in candidate_ids}
