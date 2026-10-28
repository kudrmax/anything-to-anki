import pytest
from backend.domain.entities.token_data import TokenData
from backend.domain.ports.stop_words import StopWords
from backend.domain.services.candidate_filter import CandidateFilter
from backend.domain.value_objects.cefr_level import CEFRLevel


def _make_token(
    *,
    is_punct: bool = False,
    is_stop: bool = False,
    is_alpha: bool = True,
    is_propn: bool = False,
) -> TokenData:
    return TokenData(
        index=0,
        text="test",
        lemma="test",
        pos="NOUN",
        tag="NN",
        head_index=0,
        children_indices=(),
        is_punct=is_punct,
        is_stop=is_stop,
        is_alpha=is_alpha,
        is_propn=is_propn,
        sent_index=0,
    )


@pytest.mark.unit
class TestCandidateFilter:
    def setup_method(self) -> None:
        self.filter = CandidateFilter()

    def test_relevant_content_word(self) -> None:
        assert self.filter.is_relevant_token(_make_token()) is True

    def test_excludes_punctuation(self) -> None:
        assert self.filter.is_relevant_token(_make_token(is_punct=True)) is False

    def test_excludes_stop_words(self) -> None:
        assert self.filter.is_relevant_token(_make_token(is_stop=True)) is False

    def test_excludes_proper_nouns(self) -> None:
        assert self.filter.is_relevant_token(_make_token(is_propn=True)) is False

    def test_excludes_non_alpha(self) -> None:
        assert self.filter.is_relevant_token(_make_token(is_alpha=False)) is False

    def test_is_learned_at_user_level(self) -> None:
        assert self.filter.is_learned_at_user_level(CEFRLevel.C1, CEFRLevel.B1) is True
        assert self.filter.is_learned_at_user_level(CEFRLevel.B1, CEFRLevel.B1) is True
        assert self.filter.is_learned_at_user_level(CEFRLevel.A2, CEFRLevel.B1) is False


class _StopWords(StopWords):
    def contains(self, lemma: str) -> bool:
        return lemma in {"to", "up", "own", "one"}


@pytest.mark.unit
class TestFunctionWord:
    def setup_method(self) -> None:
        self.filter = CandidateFilter()

    @pytest.mark.parametrize(("lemma", "pos"), [("to", "PART"), ("up", "ADP"), ("one", "NUM")])
    def test_a_stop_word_not_used_as_a_content_word_is_one(self, lemma: str, pos: str) -> None:
        assert self.filter.is_function_word(lemma, pos, _StopWords()) is True

    @pytest.mark.parametrize("pos", ["NOUN", "VERB", "ADJ"])
    def test_a_stop_word_used_as_a_content_word_is_not(self, pos: str) -> None:
        assert self.filter.is_function_word("own", pos, _StopWords()) is False

    @pytest.mark.parametrize("lemma", ["be", "have", "do"])
    def test_an_auxiliary_verb_is_one_even_as_a_verb(self, lemma: str) -> None:
        assert self.filter.is_function_word(lemma, "VERB", _StopWords()) is True

    def test_a_word_off_the_list_is_not(self) -> None:
        assert self.filter.is_function_word("glare", "PART", _StopWords()) is False
