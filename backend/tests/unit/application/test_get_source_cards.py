from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.get_source_cards import GetSourceCardsUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus


def _make_candidate(
    lemma: str,
    status: CandidateStatus,
    fragment: str = "test fragment",
    meaning: str | None = None,
    ipa: str | None = None,
) -> StoredCandidate:
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
        meaning=meaning,
        ipa=ipa,
    )


@pytest.mark.unit
class TestGetSourceCardsUseCase:
    def setup_method(self) -> None:
        self.candidate_repo = MagicMock()
        self.use_case = GetSourceCardsUseCase(
            candidate_repo=self.candidate_repo,
        )

    def test_returns_only_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to burnout quickly", meaning="physical collapse"),
            _make_candidate("pursuit", CandidateStatus.SKIP),
            _make_candidate("relentless", CandidateStatus.PENDING),
        ]

        result = self.use_case.execute(source_id=1)

        assert len(result) == 1
        assert result[0].lemma == "burnout"

    def test_sentence_highlights_lemma(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to burnout quickly"),
        ]

        result = self.use_case.execute(source_id=1)
        assert "<b>burnout</b>" in result[0].sentence

    def test_meaning_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, meaning="physical collapse"),
        ]

        result = self.use_case.execute(source_id=1)
        assert result[0].meaning == "physical collapse"

    def test_no_meaning_becomes_none(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN),
        ]

        result = self.use_case.execute(source_id=1)
        assert result[0].meaning is None

    def test_ipa_from_candidate(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, ipa="/ˈbɜːrnaʊt/"),
        ]

        result = self.use_case.execute(source_id=1)
        assert result[0].ipa == "/ˈbɜːrnaʊt/"

    def test_empty_when_no_learn_candidates(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.SKIP),
        ]
        result = self.use_case.execute(source_id=1)
        assert result == []

    def test_sentence_highlights_inflected_form(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("run", CandidateStatus.LEARN, "she is running fast"),
        ]
        result = self.use_case.execute(source_id=1)
        assert "<b>running</b>" in result[0].sentence

    def test_sentence_strips_markdown(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, "leads to **burnout** quickly"),
        ]
        result = self.use_case.execute(source_id=1)
        assert "**" not in result[0].sentence
        assert "<b>burnout</b>" in result[0].sentence

    def test_meaning_strips_markdown_and_highlights(self) -> None:
        self.candidate_repo.get_by_source.return_value = [
            _make_candidate("burnout", CandidateStatus.LEARN, meaning="**burnout** means exhaustion"),
        ]
        result = self.use_case.execute(source_id=1)
        assert result[0].meaning is not None
        assert "**" not in result[0].meaning
        assert "<b>burnout</b>" in result[0].meaning
