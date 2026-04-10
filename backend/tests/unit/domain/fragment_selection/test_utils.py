from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.utils import (
    collect_subtree_in_sentence,
    count_content_words,
)


def _tok(
    index: int,
    text: str,
    pos: str,
    *,
    is_punct: bool = False,
    is_alpha: bool = True,
    children: tuple[int, ...] = (),
    sent_index: int = 0,
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos=pos,
        tag=pos,
        head_index=index,
        children_indices=children,
        is_punct=is_punct,
        is_stop=False,
        is_alpha=is_alpha,
        is_propn=False,
        sent_index=sent_index,
        dep="",
    )


def test_count_content_words_excludes_punct_and_non_alpha() -> None:
    tokens = [
        _tok(0, "hello", "INTJ"),
        _tok(1, ",", "PUNCT", is_punct=True, is_alpha=False),
        _tok(2, "world", "NOUN"),
        _tok(3, "123", "NUM", is_alpha=False),
    ]
    assert count_content_words(tokens, [0, 1, 2, 3]) == 2


def test_count_content_words_accepts_iterable() -> None:
    tokens = [_tok(i, f"w{i}", "NOUN") for i in range(3)]
    assert count_content_words(tokens, {0, 1, 2}) == 3


def test_collect_subtree_in_sentence_includes_root_and_children() -> None:
    tokens = [
        _tok(0, "root", "VERB", children=(1, 2)),
        _tok(1, "a", "DET"),
        _tok(2, "b", "NOUN", children=(3,)),
        _tok(3, "c", "ADJ"),
        _tok(4, "x", "NOUN", sent_index=1),
    ]
    assert collect_subtree_in_sentence(tokens, 0, 0) == {0, 1, 2, 3}


def test_collect_subtree_in_sentence_stops_at_sentence_boundary() -> None:
    tokens = [
        _tok(0, "root", "VERB", children=(1,)),
        _tok(1, "x", "NOUN", children=(2,), sent_index=1),
        _tok(2, "y", "NOUN", sent_index=1),
    ]
    assert collect_subtree_in_sentence(tokens, 0, 0) == {0}
