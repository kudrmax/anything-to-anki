import pytest
from backend.domain.entities.token_data import TokenData
from backend.domain.services.fragment_extractor import FragmentExtractor


def _make_token(
    index: int,
    text: str,
    *,
    head_index: int | None = None,
    children: tuple[int, ...] = (),
    is_punct: bool = False,
    is_stop: bool = False,
    is_alpha: bool = True,
    sent_index: int = 0,
) -> TokenData:
    """Helper to create TokenData for tests."""
    return TokenData(
        index=index,
        text=text,
        lemma=text.lower(),
        pos="NOUN",
        tag="NN",
        head_index=head_index if head_index is not None else index,
        children_indices=children,
        is_punct=is_punct,
        is_stop=is_stop,
        is_alpha=is_alpha,
        is_propn=False,
        sent_index=sent_index,
    )


@pytest.mark.unit
class TestFragmentExtractor:
    def setup_method(self) -> None:
        self.extractor = FragmentExtractor()

    def test_empty_tokens(self) -> None:
        assert self.extractor.extract([], 0) == ""

    def test_invalid_index(self) -> None:
        tokens = [_make_token(0, "hello")]
        assert self.extractor.extract(tokens, -1) == ""
        assert self.extractor.extract(tokens, 5) == ""

    def test_single_word(self) -> None:
        """A single word — returns just that word (< 3 words, head is self)."""
        tokens = [_make_token(0, "hello")]
        result = self.extractor.extract(tokens, 0)
        assert result == "hello"

    def test_normal_subtree(self) -> None:
        """Subtree with 3+ content words is used directly."""
        # "the relentless pursuit" — pursuit is head, relentless and the are children
        tokens = [
            _make_token(0, "the", head_index=2, is_stop=True, is_alpha=True),
            _make_token(1, "relentless", head_index=2),
            _make_token(2, "pursuit", children=(0, 1)),
        ]
        result = self.extractor.extract(tokens, 1)
        # relentless subtree is just "relentless" (1 word) → go to head (pursuit)
        # pursuit subtree is "the relentless pursuit" (3 words)
        assert "pursuit" in result
        assert "relentless" in result

    def test_subtree_too_small_goes_to_head(self) -> None:
        """When subtree has < 3 content words, go up to head's subtree."""
        # "often leads to burnout"
        # burnout (3) → head is leads (1)
        # leads (1) has children: often (0), to (2), burnout (3)
        tokens = [
            _make_token(0, "often", head_index=1, is_stop=True),
            _make_token(1, "leads", children=(0, 2, 3)),
            _make_token(2, "to", head_index=1, is_stop=True),
            _make_token(3, "burnout", head_index=1),
        ]
        result = self.extractor.extract(tokens, 3)
        # burnout subtree = just "burnout" (1 word) → go to head (leads)
        # leads subtree = all 4 tokens, 2 content words (leads, burnout)
        # Still < 3 content? leads + burnout = 2 → go to sentence
        assert "burnout" in result

    def test_large_subtree_trimmed_to_window(self) -> None:
        """When subtree > 12 content words, trim to ±5 window."""
        # Create 15 content words in one sentence
        tokens = [
            _make_token(i, f"word{i}", head_index=7, children=())
            for i in range(15)
        ]
        # Make token 7 the root with all others as children
        tokens[7] = _make_token(
            7, "target", children=tuple(i for i in range(15) if i != 7)
        )

        result = self.extractor.extract(tokens, 7)
        words = result.split()
        assert len(words) <= 12  # Should be trimmed

    def test_multi_sentence_respects_boundaries(self) -> None:
        """Fragment extraction stays within the same sentence."""
        tokens = [
            _make_token(0, "Hello", sent_index=0),
            _make_token(1, ".", sent_index=0, is_punct=True, is_alpha=False),
            _make_token(2, "The", sent_index=1, is_stop=True),
            _make_token(3, "cat", sent_index=1, head_index=4),
            _make_token(4, "sat", sent_index=1, children=(2, 3)),
        ]
        result = self.extractor.extract(tokens, 3)
        assert "Hello" not in result

    def test_extract_indices_returns_sorted(self) -> None:
        tokens = [
            _make_token(0, "the", head_index=1, is_stop=True),
            _make_token(1, "cat", children=(0,)),
        ]
        indices = self.extractor.extract_indices(tokens, 1)
        assert indices == sorted(indices)

    def test_short_sentence_returns_full_sentence(self) -> None:
        """Если предложение ≤ MAX_FRAGMENT_WORDS content words — возвращается целиком."""
        # "I tell you my darkest whimsical story" — 5 content words (tell, darkest, whimsical, story + you)
        # target = whimsical (index 5), его синтаксическое поддерево = 1 слово,
        # но предложение короткое — берётся целиком.
        tokens = [
            _make_token(0, "I", head_index=1, is_stop=True),
            _make_token(1, "tell", children=(0, 2, 6)),
            _make_token(2, "you", head_index=1, is_stop=True),
            _make_token(3, "my", head_index=6, is_stop=True),
            _make_token(4, "darkest", head_index=6, children=(5,)),
            _make_token(5, "whimsical", head_index=4),
            _make_token(6, "story", head_index=1, children=(3, 4)),
        ]
        result = self.extractor.extract(tokens, 5)
        assert "story" in result
        assert "tell" in result

    def test_long_sentence_min_raised_falls_to_window(self) -> None:
        """Длинное предложение (> MAX): маленький фрагмент (< MIN=5) → window trim."""
        # 15 слов в одном предложении; root (token 7) — голова всех остальных.
        # target = token 0: его поддерево = 1 слово, голова root → поддерево = 15 слов > MAX → trim.
        tokens = [_make_token(i, f"word{i}", head_index=7) for i in range(15)]
        tokens[7] = _make_token(7, "root", children=tuple(i for i in range(15) if i != 7))
        result = self.extractor.extract(tokens, 0)
        words = result.split()
        assert len(words) <= 11  # window ±5 + target = макс 11 токенов
