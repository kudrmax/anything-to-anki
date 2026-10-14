from __future__ import annotations

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus

from tests.phrase_support import phrase


def _candidate(polished: str | None, reverted: bool = False) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma="stale",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
        source_phrase=phrase("The air around us was stale", "stale"),
        occurrences=1,
        status=CandidateStatus.PENDING,
        polished_phrase=phrase(polished, "stale") if polished is not None else None,
        polish_reverted=reverted,
    )


@pytest.mark.unit
def test_card_shows_source_phrase_until_polished() -> None:
    candidate = _candidate(None)
    assert candidate.phrase.text == "The air around us was stale"
    assert not candidate.is_polished


@pytest.mark.unit
def test_card_shows_polished_phrase() -> None:
    candidate = _candidate("The air was stale.")
    assert candidate.phrase.text == "The air was stale."
    assert candidate.is_polished


@pytest.mark.unit
def test_reverted_card_shows_source_phrase() -> None:
    candidate = _candidate("The air was stale.", reverted=True)
    assert candidate.phrase.text == "The air around us was stale"
    assert candidate.is_polished


@pytest.mark.unit
def test_phrase_ai_left_as_is_is_not_polished() -> None:
    assert not _candidate("The air around us was stale").is_polished
