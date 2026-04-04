import pytest
from backend.domain.entities.token_data import TokenData
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

    def test_is_above_user_level(self) -> None:
        assert self.filter.is_above_user_level(CEFRLevel.C1, CEFRLevel.B1) is True
        assert self.filter.is_above_user_level(CEFRLevel.B1, CEFRLevel.B1) is False
        assert self.filter.is_above_user_level(CEFRLevel.A1, CEFRLevel.B1) is False
