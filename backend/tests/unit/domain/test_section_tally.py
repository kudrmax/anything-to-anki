"""A source's cards counted by their sections read the same progress as the cards listed
one by one, at every threshold step."""
from __future__ import annotations

import pytest
from backend.domain.services.card_view import progress
from backend.domain.value_objects.by_step import SectionsByStep
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.frequent_word_threshold import THRESHOLD_STEPS
from backend.domain.value_objects.section_tally import EMPTY_TALLY, SectionTally

R = CandidateSection.READY
E = CandidateSection.EXTRA
P = CandidateSection.PROBABLY_KNOWN
V = CandidateSection.REVIEWED

TALLIES = (
    SectionTally({}),
    SectionTally({SectionsByStep((V,) * 8): 3}),
    SectionTally({SectionsByStep((R,) * 8): 2, SectionsByStep((V,) * 8): 1}),
    SectionTally({
        SectionsByStep((P, P, R, R, R, R, R, R)): 4,
        SectionsByStep((P, P, P, P, E, E, E, E)): 5,
        SectionsByStep((R, R, R, E, E, E, E, E)): 2,
        SectionsByStep((V,) * 8): 7,
    }),
)


@pytest.mark.unit
@pytest.mark.parametrize("tally", TALLIES)
@pytest.mark.parametrize("step", THRESHOLD_STEPS)
def test_progress_counts_as_the_cards_listed(tally: SectionTally, step: float | None) -> None:
    listed = [
        sections.at(step) for sections, count in tally.counts.items() for _ in range(count)
    ]
    assert tally.progress(step) == progress(listed)
    assert tally.cards == len(listed)


@pytest.mark.unit
def test_the_sections_of_the_step_count() -> None:
    tally = TALLIES[3]
    assert tally.progress(2.5) == DecisionProgress(decided=7, total=9)
    assert tally.progress(None) == DecisionProgress(decided=7, total=11)


@pytest.mark.unit
def test_no_cards_is_no_progress() -> None:
    assert EMPTY_TALLY.progress(None) == DecisionProgress()
    assert EMPTY_TALLY.cards == 0
