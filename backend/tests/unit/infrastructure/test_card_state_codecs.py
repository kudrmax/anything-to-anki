"""A card's values at every threshold step survive the TEXT column unchanged."""
from __future__ import annotations

from itertools import product

import pytest
from backend.domain.value_objects.by_step import NewCountsByStep, SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.frequent_word_threshold import THRESHOLD_STEPS
from backend.infrastructure.persistence.card_state_codecs import (
    NewCountsByStepCodec,
    SectionsByStepCodec,
)

pytestmark = pytest.mark.unit

STEPS = len(THRESHOLD_STEPS)


@pytest.mark.parametrize("section", list(CandidateSection))
def test_sections_round_trip_with_every_section_at_every_step(
    section: CandidateSection,
) -> None:
    for position in range(STEPS):
        others = [s for s in CandidateSection if s is not section]
        sections = SectionsByStep(tuple(
            section if i == position else others[i % len(others)] for i in range(STEPS)
        ))
        assert SectionsByStepCodec.decode(SectionsByStepCodec.encode(sections)) == sections


def test_every_pair_of_sections_round_trips() -> None:
    for first, second in product(CandidateSection, repeat=2):
        sections = SectionsByStep((first, second) * (STEPS // 2))
        assert SectionsByStepCodec.decode(SectionsByStepCodec.encode(sections)) == sections


def test_sections_are_one_letter_per_step() -> None:
    sections = SectionsByStep((
        CandidateSection.PROBABLY_KNOWN, CandidateSection.PROBABLY_KNOWN,
        CandidateSection.EXTRA, CandidateSection.EXTRA, CandidateSection.READY,
        CandidateSection.READY, CandidateSection.READY, CandidateSection.REVIEWED,
    ))
    assert SectionsByStepCodec.encode(sections) == "PPEERRRV"


@pytest.mark.parametrize(
    "counts", [(0,) * STEPS, (0, 0, 1, 1, 2, 2, 3, 3), (12, 7, 0, 105, 1, 0, 3, 40)],
)
def test_new_counts_round_trip(counts: tuple[int, ...]) -> None:
    by_step = NewCountsByStep(counts)
    assert NewCountsByStepCodec.decode(NewCountsByStepCodec.encode(by_step)) == by_step


def test_new_counts_are_stored_comma_separated_in_step_order() -> None:
    assert NewCountsByStepCodec.encode(NewCountsByStep((0, 0, 1, 1, 2, 2, 3, 3))) == (
        "0,0,1,1,2,2,3,3"
    )


def test_a_stored_value_of_the_wrong_length_is_refused() -> None:
    with pytest.raises(ValueError, match="threshold step"):
        SectionsByStepCodec.decode("RRR")
    with pytest.raises(ValueError, match="threshold step"):
        NewCountsByStepCodec.decode("0,1")


def test_an_unknown_section_letter_is_refused() -> None:
    with pytest.raises(KeyError):
        SectionsByStepCodec.decode("RRRRRRRX")
