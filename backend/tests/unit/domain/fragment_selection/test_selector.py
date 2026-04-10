from collections.abc import Sequence

from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_selection.selector import FragmentSelector
from backend.domain.value_objects.fragment_selection_config import (
    FragmentSelectionConfig,
)


def _tok(
    index: int,
    text: str,
    pos: str = "NOUN",
    *,
    tag: str | None = None,
    children: tuple[int, ...] = (),
    head_index: int | None = None,
    sent_index: int = 0,
    is_punct: bool = False,
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos=pos,
        tag=tag if tag is not None else pos,
        head_index=head_index if head_index is not None else index,
        children_indices=children,
        is_punct=is_punct,
        is_stop=False,
        is_alpha=not is_punct,
        is_propn=False,
        sent_index=sent_index,
        dep="",
    )


def test_selector_prefers_candidate_with_fewer_unknowns() -> None:
    # 7-token sentence; the verb at idx 2 spans the whole thing.
    tokens = [
        _tok(0, "The", "DET", sent_index=0),
        _tok(1, "cat", "NOUN", sent_index=0),
        _tok(
            2, "saw", "VERB", tag="VBD", sent_index=0,
            children=(1, 3, 4, 5, 6),
        ),
        _tok(3, "a", "DET", sent_index=0),
        _tok(4, "large", "ADJ", sent_index=0),
        _tok(5, "dog", "NOUN", sent_index=0),
        _tok(6, "bark", "VERB", tag="VB", sent_index=0),
    ]

    def counter(indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return sum(1 for i in indices if i == 4)

    selector = FragmentSelector(config=FragmentSelectionConfig())
    result = selector.select(
        tokens=tokens,
        target_index=1,
        protected_indices=frozenset({1}),
        unknown_counter=counter,
    )
    assert 1 in result


def test_selector_returns_cleaned_legacy_fallback_for_small_sentence() -> None:
    # Too few content words for any normal candidate to survive filter.
    tokens = [_tok(0, "cat")]

    def counter(_indices: Sequence[int], _tokens: list[TokenData]) -> int:
        return 0

    selector = FragmentSelector(config=FragmentSelectionConfig())
    result = selector.select(
        tokens=tokens,
        target_index=0,
        protected_indices=frozenset({0}),
        unknown_counter=counter,
    )
    assert 0 in result
