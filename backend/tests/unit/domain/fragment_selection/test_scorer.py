from collections.abc import Sequence

from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.scoring.scorer import DefaultScorer
from backend.domain.value_objects.fragment_selection_config import ScoringConfig


def _tok(index: int, is_alpha: bool = True, is_punct: bool = False) -> TokenData:
    return TokenData(
        index=index,
        text=f"w{index}",
        lemma=f"w{index}",
        pos="NOUN",
        tag="NN",
        head_index=index,
        children_indices=(),
        is_punct=is_punct,
        is_stop=False,
        is_alpha=is_alpha,
        is_propn=False,
        sent_index=0,
        dep="",
    )


def test_default_scorer_prefers_fewer_unknowns() -> None:
    def counter(indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return sum(1 for i in indices if i >= 3)

    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    tokens = [_tok(i) for i in range(6)]
    a = scorer.score([0, 1, 2, 3], tokens)
    b = scorer.score([0, 1, 2, 4, 5], tokens)
    assert a < b


def test_default_scorer_length_hard_cap_penalizes_long_fragments() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    cfg = ScoringConfig(length_hard_cap_content_words=3)
    scorer = DefaultScorer(config=cfg, unknown_counter=counter)
    tokens = [_tok(i) for i in range(5)]
    short = scorer.score([0, 1, 2], tokens)
    long_ = scorer.score([0, 1, 2, 3, 4], tokens)
    assert short < long_


def test_default_scorer_ignores_punct_in_content_count() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    tokens = [_tok(0), _tok(1, is_punct=True, is_alpha=False), _tok(2)]
    tup = scorer.score([0, 1, 2], tokens)
    assert tup[2] == 2
