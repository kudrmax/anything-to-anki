from __future__ import annotations

import pytest
from backend.domain.value_objects.decision_progress import DecisionProgress


@pytest.mark.unit
def test_progress_sums_across_sources() -> None:
    parts = [DecisionProgress(decided=2, total=963), DecisionProgress(decided=39, total=107)]

    assert sum(parts, DecisionProgress()) == DecisionProgress(decided=41, total=1070)
