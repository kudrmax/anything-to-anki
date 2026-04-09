from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.rendering import render_fragment


def _tok(index: int, text: str, whitespace_after: str = " ") -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos="NOUN",
        tag="NN",
        head_index=index,
        children_indices=(),
        is_punct=False,
        is_stop=False,
        is_alpha=True,
        is_propn=False,
        sent_index=0,
        dep="",
        whitespace_after=whitespace_after,
    )


def test_render_fragment_joins_tokens_with_original_whitespace() -> None:
    tokens = [_tok(0, "Hello"), _tok(1, "world", whitespace_after="")]
    assert render_fragment(tokens, [0, 1]) == "Hello world"


def test_render_fragment_sorts_indices() -> None:
    tokens = [_tok(0, "a"), _tok(1, "b", whitespace_after="")]
    assert render_fragment(tokens, [1, 0]) == "a b"


def test_render_fragment_empty() -> None:
    assert render_fragment([], []) == ""
