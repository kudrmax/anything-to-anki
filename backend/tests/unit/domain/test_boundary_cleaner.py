import pytest
from backend.domain.entities.token_data import TokenData
from backend.domain.services.boundary_cleaner import BoundaryCleaner


def _tok(
    index: int,
    text: str,
    pos: str,
    *,
    lemma: str | None = None,
    is_punct: bool = False,
    is_alpha: bool = True,
    children: tuple[int, ...] = (),
    head_index: int | None = None,
    dep: str = "",
) -> TokenData:
    return TokenData(
        index=index,
        text=text,
        lemma=lemma if lemma is not None else text.lower(),
        pos=pos,
        tag=pos,
        head_index=head_index if head_index is not None else index,
        children_indices=children,
        is_punct=is_punct,
        is_stop=False,
        is_alpha=is_alpha,
        is_propn=pos == "PROPN",
        sent_index=0,
        dep=dep,
    )


def _content(start: int, count: int) -> list[TokenData]:
    """Build `count` filler content tokens (NOUNs) starting at `start`."""
    return [_tok(start + i, f"w{start + i}", "NOUN") for i in range(count)]


@pytest.mark.unit
class TestBoundaryCleaner:
    def setup_method(self) -> None:
        self.cleaner = BoundaryCleaner()

    # ------------------------------------------------------------- left strip

    def test_strips_leading_cconj(self) -> None:
        # "And w1 w2 w3 w4 w5" → "w1 w2 w3 w4 w5"
        tokens = [_tok(0, "And", "CCONJ"), *_content(1, 5)]
        indices = list(range(6))
        result = self.cleaner.clean(tokens, indices)
        assert result == [1, 2, 3, 4, 5]

    def test_strips_leading_relativizer_that(self) -> None:
        # "that VERB w2 w3 w4 w5" — "that" before a verb should strip
        tokens = [
            _tok(0, "that", "PRON", lemma="that"),
            _tok(1, "believe", "VERB"),
            *_content(2, 4),
        ]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [1, 2, 3, 4, 5]

    def test_keeps_demonstrative_that_man(self) -> None:
        # "that man w2 w3 w4 w5" — "that" before NOUN is determiner, keep it
        tokens = [
            _tok(0, "that", "DET", lemma="that"),
            _tok(1, "man", "NOUN"),
            *_content(2, 4),
        ]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [0, 1, 2, 3, 4, 5]

    def test_strips_leading_punct(self) -> None:
        tokens = [
            _tok(0, "—", "PUNCT", is_punct=True, is_alpha=False),
            *_content(1, 5),
        ]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [1, 2, 3, 4, 5]

    # ------------------------------------------------------------ right strip

    def test_strips_trailing_cconj(self) -> None:
        # "w0..w4 but" → "w0..w4"
        tokens = [*_content(0, 5), _tok(5, "but", "CCONJ")]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [0, 1, 2, 3, 4]

    def test_strips_trailing_dangling_preposition(self) -> None:
        # "w0..w4 up to" — both ADPs dangling (no object inside fragment)
        tokens = [
            *_content(0, 5),
            _tok(5, "up", "ADP", children=()),
            _tok(6, "to", "ADP", children=()),
        ]
        result = self.cleaner.clean(tokens, list(range(7)))
        assert result == [0, 1, 2, 3, 4]

    def test_keeps_preposition_with_object_inside(self) -> None:
        # "w0..w4 to w6" — "to" has object w6 inside fragment, keep
        tokens = [
            *_content(0, 5),
            _tok(5, "to", "ADP", children=(6,)),
            _tok(6, "school", "NOUN"),
        ]
        result = self.cleaner.clean(tokens, list(range(7)))
        assert result == [0, 1, 2, 3, 4, 5, 6]

    def test_strips_trailing_determiner(self) -> None:
        # "w0..w4 no" — DET dangling at right
        tokens = [*_content(0, 5), _tok(5, "no", "DET")]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [0, 1, 2, 3, 4]

    def test_strips_trailing_subject_pronoun(self) -> None:
        # "w0..w4 they" — PRON dep=nsubj, head outside fragment → dangling
        tokens = [
            *_content(0, 5),
            _tok(5, "they", "PRON", lemma="they", dep="nsubj", head_index=99),
        ]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [0, 1, 2, 3, 4]

    def test_keeps_object_pronoun_after_preposition(self) -> None:
        # "w0 w1 w2 w3 with you" — 'you' is pobj of 'with' (in fragment) → keep
        tokens = [
            *_content(0, 4),
            _tok(4, "with", "ADP", children=(5,)),
            _tok(5, "you", "PRON", lemma="you", dep="pobj", head_index=4),
        ]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [0, 1, 2, 3, 4, 5]

    def test_keeps_sentence_final_period(self) -> None:
        tokens = [
            *_content(0, 5),
            _tok(5, ".", "PUNCT", is_punct=True, is_alpha=False),
        ]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [0, 1, 2, 3, 4, 5]

    def test_strips_trailing_comma(self) -> None:
        tokens = [
            *_content(0, 5),
            _tok(5, ",", "PUNCT", is_punct=True, is_alpha=False),
        ]
        result = self.cleaner.clean(tokens, list(range(6)))
        assert result == [0, 1, 2, 3, 4]

    # ------------------------------------------------------------ stop conditions

    def test_does_not_strip_below_min(self) -> None:
        # "And w1 w2 w3 w4 w5" — 5 content words; stripping "And" leaves 5, OK.
        # But "And w1 w2 w3 w4" — only 4 content words after strip → keep "And".
        tokens = [_tok(0, "And", "CCONJ"), *_content(1, 4)]
        result = self.cleaner.clean(tokens, list(range(5)))
        assert result == [0, 1, 2, 3, 4]  # nothing stripped

    def test_does_not_strip_protected_target(self) -> None:
        # "And w1 w2 w3 w4 w5" with target at index 0 (And) — protected.
        tokens = [_tok(0, "And", "CCONJ"), *_content(1, 5)]
        result = self.cleaner.clean(
            tokens, list(range(6)), protected_indices=frozenset({0})
        )
        assert 0 in result  # not stripped

    def test_iterative_left_strip(self) -> None:
        # Multiple strippable tokens at the left edge: punct + CCONJ
        tokens = [
            _tok(0, ",", "PUNCT", is_punct=True, is_alpha=False),
            _tok(1, "and", "CCONJ"),
            *_content(2, 5),
        ]
        result = self.cleaner.clean(tokens, list(range(7)))
        assert result == [2, 3, 4, 5, 6]

    def test_iterative_right_strip(self) -> None:
        # Multiple strippable tokens at the right edge: CCONJ + DET
        tokens = [*_content(0, 5), _tok(5, "and", "CCONJ"), _tok(6, "no", "DET")]
        result = self.cleaner.clean(tokens, list(range(7)))
        assert result == [0, 1, 2, 3, 4]

    def test_empty_indices(self) -> None:
        assert self.cleaner.clean([], []) == []

    def test_no_changes_needed(self) -> None:
        # Already clean
        tokens = _content(0, 5)
        result = self.cleaner.clean(tokens, list(range(5)))
        assert result == [0, 1, 2, 3, 4]
