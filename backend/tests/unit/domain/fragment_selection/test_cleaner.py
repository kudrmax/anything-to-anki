from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.cleanup.cleaner import (
    RuleDrivenBoundaryCleaner,
)
from backend.domain.value_objects.fragment_selection_config import CleanupConfig


def _tok(
    index: int, text: str, pos: str = "NOUN", *, is_punct: bool = False
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos=pos,
        tag=pos,
        head_index=index,
        children_indices=(),
        is_punct=is_punct,
        is_stop=False,
        is_alpha=not is_punct,
        is_propn=False,
        sent_index=0,
        dep="",
    )


def test_rule_driven_cleaner_strips_both_edges() -> None:
    tokens = (
        [_tok(0, "and", "CCONJ"), _tok(1, "the", "DET")]
        + [_tok(i, f"w{i}") for i in range(2, 7)]
        + [_tok(7, ",", "PUNCT", is_punct=True)]
    )
    cleaner = RuleDrivenBoundaryCleaner(CleanupConfig())
    # Note: "the" is DET on left — our left rules don't strip DET.
    # So only the "and" on the left and the "," on the right get trimmed.
    assert cleaner.clean(tokens, [0, 1, 2, 3, 4, 5, 6, 7]) == [1, 2, 3, 4, 5, 6]


def test_rule_driven_cleaner_protects_target() -> None:
    tokens = [_tok(0, "and", "CCONJ")] + [_tok(i, f"w{i}") for i in range(1, 6)]
    cleaner = RuleDrivenBoundaryCleaner(CleanupConfig())
    cleaned = cleaner.clean(
        tokens, [0, 1, 2, 3, 4, 5], protected_indices=frozenset({0})
    )
    assert 0 in cleaned


def test_rule_driven_cleaner_respects_min_content_words_allowing_strip() -> None:
    # 5 content tokens + "and" — stripping leaves 5 content words, OK.
    tokens = [_tok(i, f"w{i}") for i in range(5)] + [_tok(5, "and", "CCONJ")]
    cleaner = RuleDrivenBoundaryCleaner(CleanupConfig())
    assert cleaner.clean(tokens, [0, 1, 2, 3, 4, 5]) == [0, 1, 2, 3, 4]


def test_rule_driven_cleaner_respects_min_content_words_blocking_strip() -> None:
    # 4 content tokens + "and" — stripping would leave 4 → do not strip.
    tokens = [_tok(i, f"w{i}") for i in range(4)] + [_tok(4, "and", "CCONJ")]
    cleaner = RuleDrivenBoundaryCleaner(CleanupConfig())
    assert cleaner.clean(tokens, [0, 1, 2, 3, 4]) == [0, 1, 2, 3, 4]
