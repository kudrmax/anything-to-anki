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

    @pytest.mark.parametrize("score", [
        _score(),
        _score(overflow=3, incomplete=1, boundary=2, unknowns=4, content=17),
        _score(unknowns=999, content=999),
    ])
    def test_a_number_unpacks_to_its_score(self, score: FragmentScore) -> None:
        assert FragmentScore.from_number(score.as_number()) == score

    def test_a_capped_field_unpacks_capped(self) -> None:
        unpacked = FragmentScore.from_number(WORST_FRAGMENT_SCORE.as_number())
        assert unpacked == _score(overflow=999, incomplete=1, boundary=999, unknowns=999,
                                  content=999)

    def test_new_unknowns_change_that_field_only(self) -> None:
        score = _score(boundary=2, unknowns=1, content=8)
        assert score.with_unknowns(3) == _score(boundary=2, unknowns=3, content=8)
