import pytest
from backend.domain.services.known_word_filter import KnownWordFilter


@pytest.mark.unit
class TestKnownWordFilter:
    def test_exact_match_is_known(self) -> None:
        f = KnownWordFilter({("run", "VERB")})
        assert f.is_known("run") is True

    def test_wildcard_match_is_known(self) -> None:
        f = KnownWordFilter({("run", None)})
        assert f.is_known("run") is True

    def test_word_known_as_another_part_of_speech_is_known(self) -> None:
        f = KnownWordFilter({("divorce", "NOUN")})
        assert f.is_known("divorce") is True

    def test_empty_set_not_known(self) -> None:
        f = KnownWordFilter(set())
        assert f.is_known("run") is False

    def test_other_lemmas_not_known(self) -> None:
        f = KnownWordFilter({("run", None)})
        assert f.is_known("fun") is False

    def test_match_ignores_case(self) -> None:
        f = KnownWordFilter({("Run", "VERB")})
        assert f.is_known("RUN") is True

    def test_phrasal_verb_lemma_is_matched_whole(self) -> None:
        f = KnownWordFilter({("make up", "VERB")})
        assert f.is_known("make up") is True
        assert f.is_known("make") is False

    def test_known_lemmas_are_lowercased(self) -> None:
        f = KnownWordFilter({("Run", "VERB"), ("walk", None)})
        assert f.known_lemmas == frozenset({"run", "walk"})
