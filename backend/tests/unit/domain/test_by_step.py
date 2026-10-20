"""A card's values at every threshold step: one per step, read by the step's zipf."""
from __future__ import annotations

import pytest
from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.frequent_word_threshold import THRESHOLD_STEPS

pytestmark = pytest.mark.unit

COUNTS = (7, 6, 5, 4, 3, 2, 1, 0)


def test_a_value_is_read_by_its_step() -> None:
    counts = NewCountsByStep(COUNTS)
    assert [counts.at(step) for step in THRESHOLD_STEPS] == list(COUNTS)
    sections = SectionsByStep(
        (CandidateSection.PROBABLY_KNOWN,) * 7 + (CandidateSection.READY,),
    )
    assert sections.at(None) is CandidateSection.READY
    assert sections.at(2.5) is CandidateSection.PROBABLY_KNOWN


def test_a_zipf_that_is_no_step_is_refused() -> None:
    with pytest.raises(ValueError, match="Not a threshold step"):
        NewCountsByStep(COUNTS).at(4.2)


@pytest.mark.parametrize("length", [0, len(THRESHOLD_STEPS) - 1, len(THRESHOLD_STEPS) + 1])
def test_one_value_per_step_exactly(length: int) -> None:
    with pytest.raises(ValueError, match="one per threshold step"):
        NewCountsByStep((0,) * length)
    with pytest.raises(ValueError, match="one per threshold step"):
        SectionsByStep((CandidateSection.READY,) * length)


def test_a_count_is_never_negative() -> None:
    with pytest.raises(ValueError, match="negative"):
        NewCountsByStep((0, 0, 0, -1, 0, 0, 0, 0))
