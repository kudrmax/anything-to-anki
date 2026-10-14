"""Decision phrases for export tests that seed card-shaped words into repository mocks."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.occurrence import Occurrence
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from backend.domain.entities.stored_candidate import StoredCandidate


def decision_of(candidate: StoredCandidate) -> Occurrence:
    """The phrase of a word's decision as the card-shaped word shows it; a word with cloze
    markup was decided as a cloze. The phrase id is the word id."""
    assert candidate.id is not None
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
