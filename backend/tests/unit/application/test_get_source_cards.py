from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_source_cards import GetSourceCardsUseCase
from backend.domain.entities.dictionary_entry import DictionaryEntry
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus


def _make_candidate(lemma: str, status: CandidateStatus, fragment: str = "test fragment") -> StoredCandidate:
    return StoredCandidate(
        id=1,
        source_id=1,
        lemma=lemma,
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=3.5,
        is_sweet_spot=True,
        context_fragment=fragment,
        fragment_purity="clean",
        occurrences=1,
        status=status,
    )


@pytest.mark.unit
class TestGetSourceCardsUseCase:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.dictionary_provider = MagicMock()
        self.use_case = GetSourceCardsUseCase(
            candidate_repo=self.candidate_repo,
            dictionary_provider=self.dictionary_provider,
        )

    def test_returns_only_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to burnout quickly"),
            _make_candidate("pursuit", CandidateStatus.SKIP),
            _make_candidate("relentless", CandidateStatus.PENDING),
        ]
        self.dictionary_provider.get_entry.return_value = DictionaryEntry(
            lemma="burnout", pos="NOUN", definition="physical collapse", ipa="/ˈbɜːrnaʊt/"
        )

        result = self.use_case.execute(source_id=1)

        assert len(result) == 1
        assert result[0].lemma == "burnout"

    def test_sentence_highlights_lemma(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to burnout quickly"),
        ]
        self.dictionary_provider.get_entry.return_value = DictionaryEntry(
            lemma="burnout", pos="NOUN", definition="physical collapse", ipa=None
        )

        result = self.use_case.execute(source_id=1)
        assert "<b>burnout</b>" in result[0].sentence

    def test_no_definition_becomes_none(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]
        self.dictionary_provider.get_entry.return_value = DictionaryEntry(
            lemma="burnout", pos="NOUN", definition="No definition found", ipa=None
        )

        result = self.use_case.execute(source_id=1)
        assert result[0].meaning is None

    def test_empty_when_no_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.SKIP),
        ]
        result = self.use_case.execute(source_id=1)
        assert result == []
