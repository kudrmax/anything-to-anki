from collections.abc import Sequence
from dataclasses import replace

from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.scoring.scorer import DefaultScorer
from backend.domain.value_objects.fragment_selection_config import ScoringConfig


def _tok(
    index: int,
    is_alpha: bool = True,
    is_punct: bool = False,
    *,
    text: str = "",
    pos: str = "NOUN",
    dep: str = "",
    head: int | None = None,
    children: tuple[int, ...] = (),
) -> TokenData:
    return TokenData(
        index=index,
        text=text or f"w{index}",
        lemma=(text or f"w{index}").lower(),
        pos=pos,
        tag="NN",
        head_index=index if head is None else head,
        children_indices=children,
        is_punct=is_punct,
        is_stop=False,
        is_alpha=is_alpha,
        is_propn=False,
        sent_index=0,
        dep=dep,
    )


def _sentence_with_two_unknowns() -> list[TokenData]:
    """'you sure have a lot of books about lesbians' — 'have' is the root."""
    return [
        _tok(0, text="you", pos="PRON", dep="nsubj", head=2),
        _tok(1, text="sure", pos="ADV", dep="advmod", head=2),
        _tok(2, text="have", pos="VERB", dep="ROOT", children=(0, 1, 4)),
        _tok(3, text="a", pos="DET", dep="det", head=4),
        _tok(4, text="lot", pos="NOUN", dep="dobj", head=2, children=(3, 5)),
        _tok(5, text="of", pos="ADP", dep="prep", head=4, children=(6,)),
        _tok(6, text="books", pos="NOUN", dep="pobj", head=5, children=(7,)),
        _tok(7, text="about", pos="ADP", dep="prep", head=6, children=(8,)),
        _tok(8, text="lesbians", pos="NOUN", dep="pobj", head=7),
    ]


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
    score = scorer.score([0, 1, 2], tokens)
    assert score.content_count == 2


def test_whole_sentence_beats_cut_piece_with_fewer_unknowns() -> None:
    def counter(indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return int(1 in indices)  # "sure" is the second unknown word

    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    tokens = _sentence_with_two_unknowns()
    sentence = scorer.score(list(range(9)), tokens)
    piece = scorer.score([5, 6, 7, 8], tokens)
    assert piece.unknowns < sentence.unknowns
    assert sentence < piece


def test_sentence_with_cut_off_tail_is_not_complete() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    tokens = _sentence_with_two_unknowns()
    assert scorer.score([0, 1, 2, 3, 4], tokens).incomplete == 1
    assert scorer.score(list(range(9)), tokens).incomplete == 0


def test_dropping_only_function_words_keeps_clause_complete() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    tokens = _sentence_with_two_unknowns()
    tokens[0] = replace(tokens[0], is_stop=True)  # "you" trimmed by edge cleanup
    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    assert scorer.score(list(range(1, 9)), tokens).incomplete == 0


def test_verb_with_its_subject_is_a_complete_clause() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    tokens = [
        _tok(0, text="said", pos="VERB", dep="ROOT", children=(3,)),
        _tok(1, text="they", pos="PRON", dep="nsubj", head=3),
        _tok(2, text="were", pos="AUX", dep="aux", head=3),
        _tok(3, text="divorcing", pos="VERB", dep="ccomp", head=0, children=(1, 2)),
    ]
    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    assert scorer.score([1, 2, 3], tokens).incomplete == 0


def test_verb_without_subject_is_not_a_complete_clause() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    tokens = [
        _tok(0, text="came", pos="VERB", dep="ROOT", children=(2,)),
        _tok(1, text="to", pos="PART", dep="aux", head=2),
        _tok(2, text="pick", pos="VERB", dep="advcl", head=0, children=(1,)),
    ]
    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    assert scorer.score([1, 2], tokens).incomplete == 1


def test_cutting_off_an_attached_clause_keeps_clause_complete() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    tokens = [
        _tok(0, text="I", pos="PRON", dep="nsubj", head=1),
        _tok(1, text="win", pos="VERB", dep="ROOT", children=(0, 2, 3, 5)),
        _tok(2, text="arguments", pos="NOUN", dep="dobj", head=1),
        _tok(3, text="but", pos="CCONJ", dep="cc", head=1),
        _tok(4, text="trust", pos="VERB", dep="conj", head=1, children=(6,)),
        _tok(5, text="please", pos="INTJ", dep="intj", head=1),
        _tok(6, text="me", pos="PRON", dep="dobj", head=4),
    ]
    tokens[1] = replace(tokens[1], children_indices=(0, 2, 3, 4, 5))
    tokens[3] = replace(tokens[3], is_stop=True)
    tokens[5] = replace(tokens[5], is_stop=True)
    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    assert scorer.score([0, 1, 2], tokens).incomplete == 0


def _stood_up_letting_the_bag_fall() -> list[TokenData]:
    """'I stood up letting the bag fall' — 'letting' is an advcl of 'stood'."""
    tokens = [
        _tok(0, text="I", pos="PRON", dep="nsubj", head=1),
        _tok(1, text="stood", pos="VERB", dep="ROOT", children=(0, 2, 3)),
        _tok(2, text="up", pos="ADP", dep="prt", head=1),
        _tok(3, text="letting", pos="VERB", dep="advcl", head=1, children=(6,)),
        _tok(4, text="the", pos="DET", dep="det", head=5),
        _tok(5, text="bag", pos="NOUN", dep="nsubj", head=6, children=(4,)),
        _tok(6, text="fall", pos="VERB", dep="ccomp", head=3, children=(5,)),
    ]
    return [replace(t, is_stop=t.text in {"I", "up", "the"}) for t in tokens]


def test_half_of_an_attached_clause_is_not_complete() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    tokens = _stood_up_letting_the_bag_fall()
    assert scorer.score([0, 1, 2, 3, 4, 5], tokens).incomplete == 1
    assert scorer.score([0, 1, 2], tokens).incomplete == 0
    assert scorer.score(list(range(7)), tokens).incomplete == 0


def test_piece_of_another_clause_glued_on_is_not_complete() -> None:
    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    tokens = [
        _tok(0, text="I", pos="PRON", dep="nsubj", head=1),
        _tok(1, text="accomplished", pos="VERB", dep="ROOT", children=(0, 2, 3, 6)),
        _tok(2, text="nothing", pos="PRON", dep="dobj", head=1),
        _tok(3, text="and", pos="CCONJ", dep="cc", head=1),
        _tok(4, text="my", pos="PRON", dep="poss", head=5),
        _tok(5, text="shoes", pos="NOUN", dep="nsubj", head=6, children=(4,)),
        _tok(6, text="slipped", pos="VERB", dep="conj", head=1, children=(5,)),
    ]
    tokens = [replace(t, is_stop=t.text in {"I", "nothing", "and", "my"}) for t in tokens]
    scorer = DefaultScorer(config=ScoringConfig(), unknown_counter=counter)
    assert scorer.score([0, 1, 2, 3, 4, 5], tokens).incomplete == 1
    assert scorer.score([0, 1, 2], tokens).incomplete == 0
