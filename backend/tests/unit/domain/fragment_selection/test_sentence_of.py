from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.utils import sentence_of


def _tok(index: int, sent_index: int) -> TokenData:
    return TokenData(
        index=index,
        text=f"w{index}",
        lemma=f"w{index}",
        pos="NOUN",
        tag="NN",
        head_index=index,
        children_indices=(),
        is_punct=False,
        is_stop=False,
        is_alpha=True,
        is_propn=False,
        sent_index=sent_index,
    )


def _tokens(*sentence_lengths: int) -> list[TokenData]:
    tokens: list[TokenData] = []
    for sent, length in enumerate(sentence_lengths):
        tokens.extend(_tok(len(tokens), sent) for _ in range(length))
    return tokens


def test_tokens_of_the_target_sentence_only() -> None:
    tokens = _tokens(3, 4, 2)

    assert [t.index for t in sentence_of(tokens, 4)] == [3, 4, 5, 6]


def test_first_and_last_sentences() -> None:
    tokens = _tokens(2, 3)

    assert [t.index for t in sentence_of(tokens, 0)] == [0, 1]
    assert [t.index for t in sentence_of(tokens, 4)] == [2, 3, 4]


def test_one_sentence_text() -> None:
    tokens = _tokens(5)

    assert [t.index for t in sentence_of(tokens, 2)] == [0, 1, 2, 3, 4]
