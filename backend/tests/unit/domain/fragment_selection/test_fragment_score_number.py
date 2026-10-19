from __future__ import annotations

import pytest
from backend.domain.services.fragment_selection.scoring.scorer import (
    WORST_FRAGMENT_SCORE,
    FragmentScore,
)


def _score(
    overflow: int = 0, incomplete: int = 0, boundary: int = 0, unknowns: int = 0, content: int = 0,
) -> FragmentScore:
    return FragmentScore(
        length_overflow=overflow, incomplete=incomplete, boundary_penalty=boundary,
        unknowns=unknowns, content_count=content,
    )


@pytest.mark.unit
class TestFragmentScoreNumber:
    def test_number_keeps_the_order_of_scores(self) -> None:
        scores = [
            _score(content=3),
            _score(content=40),
            _score(unknowns=1),
            _score(unknowns=1, content=999),
            _score(boundary=1),
            _score(incomplete=1),
            _score(overflow=1),
            WORST_FRAGMENT_SCORE,
        ]
        assert sorted(scores) == scores
        numbers = [s.as_number() for s in scores]
        assert numbers == sorted(numbers)
        assert len(set(numbers)) == len(numbers)

    def test_worst_score_is_not_beaten_by_any_real_one(self) -> None:
        assert _score(overflow=5, incomplete=1, boundary=9).as_number() < (
            WORST_FRAGMENT_SCORE.as_number()
        )
