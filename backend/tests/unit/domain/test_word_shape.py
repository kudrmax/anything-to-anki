import pytest
from backend.domain.services.word_shape import is_plain_word


@pytest.mark.unit
class TestIsPlainWord:
    @pytest.mark.parametrize("lemma", ["military", "o'clock", "ma'am", "well-known", "café"])
    def test_a_word(self, lemma: str) -> None:
        assert is_plain_word(lemma)

    @pytest.mark.parametrize(
        "lemma",
        ["10th", "2030s", "mp3", "0.", "e.g.", "a.m.", "expect'", "seemed!", "na´ve", "'em", ""],
    )
    def test_not_a_word(self, lemma: str) -> None:
        assert not is_plain_word(lemma)
