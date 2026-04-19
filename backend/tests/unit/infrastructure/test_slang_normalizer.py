from __future__ import annotations

import pytest
from backend.infrastructure.adapters.slang_normalizer import SlangNormalizer


class TestSlangNormalizer:
    def setup_method(self) -> None:
        self.normalizer = SlangNormalizer()

    # --- Specific contraction rules ---

    @pytest.mark.parametrize(
        ("input_text", "expected"),
        [
            ("I wanna buy something", "I want to buy something"),
            ("She gunna be late", "She going to be late"),
            ("He's tryna help", "He's trying to help"),
            ("I dunno what happened", "I do not know what happened"),
            ("Lemme see that", "Let me see that"),
            ("Gimme a break", "Give me a break"),
            ("I coulda done it", "I could have done it"),
            ("I woulda gone", "I would have gone"),
            ("I shoulda known", "I should have known"),
            ("She kinda likes it", "She kind of likes it"),
            ("It's sorta weird", "It's sort of weird"),
            ("Whatcha doing", "What are you doing"),
            ("Gotcha covered", "Got you covered"),
            ("Y'all should come", "You all should come"),
            ("Ain't that right", "Is not that right"),
            ("Give 'em a break", "Give them a break"),
        ],
    )
    def test_specific_contractions(self, input_text: str, expected: str) -> None:
        assert self.normalizer.normalize(input_text) == expected

    # --- General -in' → -ing rule ---

    @pytest.mark.parametrize(
        ("input_text", "expected"),
        [
            ("I'm goin' to the store", "I'm going to the store"),
            ("She's runnin' fast", "She's running fast"),
            ("He was doin' nothing", "He was doing nothing"),
            ("They're comin' home", "They're coming home"),
        ],
    )
    def test_dropped_g_pattern(self, input_text: str, expected: str) -> None:
        assert self.normalizer.normalize(input_text) == expected

    # --- Case preservation ---

    def test_preserves_lowercase(self) -> None:
        assert self.normalizer.normalize("wanna go") == "want to go"

    def test_preserves_capitalized(self) -> None:
        assert self.normalizer.normalize("Wanna go") == "Want to go"

    def test_preserves_all_caps(self) -> None:
        assert self.normalizer.normalize("WANNA go") == "WANT TO go"

    # --- No false positives ---

    def test_no_replacement_inside_word(self) -> None:
        text = "Savannah is beautiful"
        assert self.normalizer.normalize(text) == text

    def test_no_replacement_for_standard_english(self) -> None:
        text = "I want to buy something nice"
        assert self.normalizer.normalize(text) == text

    # --- Multiple contractions ---

    def test_multiple_contractions_in_one_sentence(self) -> None:
        text = "I wanna know whatcha doin'"
        expected = "I want to know what are you doing"
        assert self.normalizer.normalize(text) == expected

    # --- Passthrough ---

    def test_empty_string(self) -> None:
        assert self.normalizer.normalize("") == ""

    def test_text_without_contractions(self) -> None:
        text = "The quick brown fox jumps over the lazy dog"
        assert self.normalizer.normalize(text) == text

    # --- spaCy-handled forms are NOT in the dictionary ---

    def test_gonna_not_normalized(self) -> None:
        """spaCy already handles 'gonna' correctly, so we don't touch it."""
        text = "I'm gonna go"
        assert self.normalizer.normalize(text) == text

    def test_gotta_not_normalized(self) -> None:
        """spaCy already handles 'gotta' correctly, so we don't touch it."""
        text = "I gotta go"
        assert self.normalizer.normalize(text) == text
