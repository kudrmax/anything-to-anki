from __future__ import annotations

import pytest
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.decision_progress import DecisionProgress


@pytest.mark.unit
def test_every_status_but_pending_counts_as_decided() -> None:
    progress = DecisionProgress.of_counts({
        CandidateStatus.PENDING: 5,
        CandidateStatus.LEARN: 2,
        CandidateStatus.KNOWN: 3,
        CandidateStatus.SKIP: 1,
    })

    assert progress == DecisionProgress(decided=6, total=11)


@pytest.mark.unit
def test_of_statuses_matches_of_counts() -> None:
    statuses = [CandidateStatus.PENDING, CandidateStatus.LEARN, CandidateStatus.LEARN]

    assert DecisionProgress.of_statuses(statuses) == DecisionProgress(decided=2, total=3)


@pytest.mark.unit
def test_progress_sums_across_sources() -> None:
    parts = [DecisionProgress(decided=2, total=963), DecisionProgress(decided=39, total=107)]

    assert sum(parts, DecisionProgress()) == DecisionProgress(decided=41, total=1070)
