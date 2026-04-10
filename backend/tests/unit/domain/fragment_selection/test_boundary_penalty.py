"""Tests for the boundary penalty component of DefaultScorer.

Boundary penalty counts critical dependency arcs that cross the fragment
boundary --- arcs where the dep relation is in ``ScoringConfig.critical_deps``.

Left penalty: tokens inside whose head is outside (to the left) with a critical dep.
Right penalty: children of inside tokens that are outside (to the right) with a critical dep.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.scoring.scorer import DefaultScorer
from backend.domain.value_objects.fragment_selection_config import ScoringConfig

if TYPE_CHECKING:
    from collections.abc import Sequence


def _tok(
    index: int,
    text: str,
    pos: str = "NOUN",
    *,
    tag: str = "",
    dep: str = "",
    children: tuple[int, ...] = (),
    head_index: int | None = None,
    sent_index: int = 0,
    is_punct: bool = False,
    is_stop: bool = False,
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos=pos,
        tag=tag or pos,
        head_index=head_index if head_index is not None else index,
        children_indices=children,
        is_punct=is_punct,
        is_stop=is_stop,
        is_alpha=not is_punct,
        is_propn=False,
        sent_index=sent_index,
        dep=dep,
    )


def _zero_counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
    return 0


class TestBoundaryPenaltyLeftEdge:
    """Left penalty: token inside has head outside-left with critical dep."""

    def test_pobj_head_outside_left_incurs_penalty(self) -> None:
        """'arc building ...' where arc.dep=pobj and head 'with' is outside."""
        tokens = [
            _tok(0, "with", "ADP", dep="prep", head_index=5, children=(1,)),
            _tok(1, "an", "DET", dep="det", head_index=3),
            _tok(2, "overall", "ADJ", dep="amod", head_index=3),
            _tok(3, "arc", "NOUN", dep="pobj", head_index=0, children=(1, 2, 4)),
            _tok(4, "building", "VERB", dep="acl", head_index=3, children=(6,)),
            _tok(5, "ran", "VERB", dep="ROOT", head_index=5, children=(0,)),
            _tok(6, "conclusion", "NOUN", dep="dobj", head_index=4),
        ]
        scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=_zero_counter)

        # Fragment WITHOUT "with": indices [1..6] --- "arc" has pobj head outside
        score_without = scorer.score([1, 2, 3, 4, 6], tokens)
        # Fragment WITH "with": indices [0..6] --- no critical cuts
        score_with = scorer.score([0, 1, 2, 3, 4, 6], tokens)

        assert score_with < score_without, (
            "Fragment including PP head 'with' should score better"
        )

    def test_no_penalty_when_head_inside(self) -> None:
        """All heads inside the fragment -> boundary penalty = 0."""
        tokens = [
            _tok(0, "The", "DET", dep="det", head_index=1),
            _tok(1, "cat", "NOUN", dep="nsubj", head_index=2, children=(0,)),
            _tok(2, "sat", "VERB", dep="ROOT", head_index=2, children=(1,)),
        ]
        scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=_zero_counter)
        score = scorer.score([0, 1, 2], tokens)
        # boundary_penalty is the second element (index 1)
        assert score[1] == 0

    def test_attr_head_outside_left_incurs_penalty(self) -> None:
        """'no need ...' where need.dep=attr, head 'is' is outside."""
        tokens = [
            _tok(0, "there", "PRON", dep="expl", head_index=1),
            _tok(1, "'s", "AUX", dep="ROOT", head_index=1, children=(0, 2)),
            _tok(2, "need", "NOUN", dep="attr", head_index=1, children=(3, 4)),
            _tok(3, "no", "DET", dep="det", head_index=2),
            _tok(4, "to", "PART", dep="aux", head_index=5),
            _tok(5, "finish", "VERB", dep="xcomp", head_index=2, children=(4,)),
        ]
        scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=_zero_counter)

        # Without "there's": [2,3,4,5] --- "need" has attr head outside
        score_without = scorer.score([2, 3, 4, 5], tokens)
        # With "there's": [0,1,2,3,4,5] --- all heads inside
        score_with = scorer.score([0, 1, 2, 3, 4, 5], tokens)

        assert score_with < score_without


class TestBoundaryPenaltyRightEdge:
    """Right penalty: child of inside token is outside-right with critical dep."""

    def test_xcomp_child_outside_right_incurs_penalty(self) -> None:
        """'fic is considered' where considered has xcomp child 'hit' outside."""
        tokens = [
            _tok(0, "fic", "NOUN", dep="nsubjpass", head_index=2, children=()),
            _tok(1, "is", "AUX", dep="auxpass", head_index=2),
            _tok(2, "considered", "VERB", dep="ROOT", head_index=2, children=(0, 1, 3)),
            _tok(3, "hit", "VERB", dep="xcomp", head_index=2, children=(4,)),
            _tok(4, "stride", "NOUN", dep="dobj", head_index=3),
        ]
        scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=_zero_counter)

        # Without xcomp chain: [0,1,2] --- "considered" has xcomp child outside
        score_without = scorer.score([0, 1, 2], tokens)
        # With xcomp chain: [0,1,2,3,4] --- all children inside
        score_with = scorer.score([0, 1, 2, 3, 4], tokens)

        assert score_with < score_without

    def test_dobj_child_outside_right_incurs_penalty(self) -> None:
        """'he hit' without 'stride' -> dobj child outside."""
        tokens = [
            _tok(0, "he", "PRON", dep="nsubj", head_index=1),
            _tok(1, "hit", "VERB", dep="ROOT", head_index=1, children=(0, 2)),
            _tok(2, "stride", "NOUN", dep="dobj", head_index=1),
        ]
        scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=_zero_counter)

        score_without = scorer.score([0, 1], tokens)
        score_with = scorer.score([0, 1, 2], tokens)

        assert score_with < score_without

    def test_no_penalty_when_children_inside(self) -> None:
        """All children of edge tokens are inside -> no right penalty."""
        tokens = [
            _tok(0, "he", "PRON", dep="nsubj", head_index=1),
            _tok(1, "hit", "VERB", dep="ROOT", head_index=1, children=(0, 2)),
            _tok(2, "it", "PRON", dep="dobj", head_index=1),
        ]
        scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=_zero_counter)
        score = scorer.score([0, 1, 2], tokens)
        assert score[1] == 0


class TestBoundaryPenaltyNonCriticalDeps:
    """Non-critical deps (det, advmod, etc.) should NOT incur penalty."""

    def test_det_head_outside_no_penalty(self) -> None:
        """Determiner whose head is outside is not a critical cut."""
        tokens = [
            _tok(0, "a", "DET", dep="det", head_index=1),
            _tok(1, "cat", "NOUN", dep="nsubj", head_index=2, children=(0,)),
            _tok(2, "sat", "VERB", dep="ROOT", head_index=2, children=(1,)),
        ]
        scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=_zero_counter)
        # Fragment [1, 2] --- "a" is outside but dep=det -> not critical
        score = scorer.score([1, 2], tokens)
        assert score[1] == 0

    def test_advmod_child_outside_no_penalty(self) -> None:
        """Adverb child outside is not a critical cut."""
        tokens = [
            _tok(0, "cat", "NOUN", dep="nsubj", head_index=1),
            _tok(1, "ran", "VERB", dep="ROOT", head_index=1, children=(0, 2)),
            _tok(2, "quickly", "ADV", dep="advmod", head_index=1),
        ]
        scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=_zero_counter)
        # Fragment [0, 1] --- "quickly" is child outside but dep=advmod -> not critical
        score = scorer.score([0, 1], tokens)
        assert score[1] == 0
