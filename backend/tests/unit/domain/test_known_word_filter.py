import pytest
from backend.domain.services.known_word_filter import KnownWordFilter


@pytest.mark.unit
class TestKnownWordFilter:
    def test_exact_match_is_known(self) -> None:
        f = KnownWordFilter({("run", "VERB")})
        assert f.is_known("run", "VERB") is True

    def test_wildcard_match_is_known(self) -> None:
        f = KnownWordFilter({("run", None)})
        assert f.is_known("run", "VERB") is True

    def test_different_pos_not_known(self) -> None:
        f = KnownWordFilter({("run", "NOUN")})
        assert f.is_known("run", "VERB") is False

    def test_empty_set_not_known(self) -> None:
        f = KnownWordFilter(set())
        assert f.is_known("run", "VERB") is False

    def test_wildcard_does_not_match_other_lemmas(self) -> None:
        f = KnownWordFilter({("run", None)})
        assert f.is_known("fun", "VERB") is False

    def test_exact_and_wildcard_coexist_same_pos(self) -> None:
        f = KnownWordFilter({("run", "VERB"), ("run", None)})
        assert f.is_known("run", "VERB") is True

    def test_exact_and_wildcard_coexist_different_pos(self) -> None:
        f = KnownWordFilter({("run", "VERB"), ("run", None)})
        assert f.is_known("run", "NOUN") is True

    def test_exact_only_different_pos_not_known(self) -> None:
        f = KnownWordFilter({("run", "VERB")})
        assert f.is_known("run", "NOUN") is False

    def test_multiple_lemmas_independent(self) -> None:
        f = KnownWordFilter({("run", None), ("walk", "VERB")})
        assert f.is_known("run", "ADJ") is True
        assert f.is_known("walk", "VERB") is True
        assert f.is_known("walk", "NOUN") is False
