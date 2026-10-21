import pytest
from backend.domain.value_objects.vocabulary import Vocabulary


@pytest.mark.unit
class TestVocabulary:
    def test_known_word_is_known(self) -> None:
        assert Vocabulary.of(known={"run"}, unknown=set()).is_known("run") is True

    def test_other_words_are_not_known(self) -> None:
        assert Vocabulary.of(known={"run"}, unknown=set()).is_known("fun") is False

    def test_match_ignores_case(self) -> None:
        vocabulary = Vocabulary.of(known={"Run"}, unknown={"Lurk"})
        assert vocabulary.is_known("RUN") is True
        assert vocabulary.is_unknown("LURK") is True

    def test_phrasal_verb_is_matched_whole(self) -> None:
        vocabulary = Vocabulary.of(known={"make up"}, unknown=set())
        assert vocabulary.is_known("make up") is True
        assert vocabulary.is_known("make") is False
