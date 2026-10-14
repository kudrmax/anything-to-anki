"""Tests for ReplaceWithExampleUseCase."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError, TargetNotInPhraseError
from backend.domain.services.phrase_building import target_by_lemma
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.usage_distribution import UsageDistribution

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase

_LEMMAS = {"ran": "run", "runs": "run"}


def _read_for(text: str, lemma: str) -> Phrase:
    found = phrase(text, lemma, lemmas=_LEMMAS)
    if not target_by_lemma(found.words, text, lemma):
        raise TargetNotInPhraseError()
    return found


def _read(text: str, spans: list[tuple[int, int]]) -> Phrase:
    whole = phrase(text, lemmas=_LEMMAS)
    target = tuple(
        i for i, word in enumerate(whole.words)
        if any(word.start < end and start < word.end for start, end in spans)
    )
    if not target:
        raise TargetNotInPhraseError()
    return whole.with_target(target)


def _candidate(
    *,
    candidate_id: int = 1,
    source_id: int = 10,
    lemma: str = "run",
    pos: str = "VERB",
    cefr_level: str | None = "B1",
    zipf_frequency: float = 4.0,
    context_fragment: str = "He ran to the store.",
    occurrences: int = 2,
    is_phrasal_verb: bool = False,
    cefr_breakdown: CEFRBreakdown | None = None,
    usage_distribution: UsageDistribution | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=candidate_id,
        source_id=source_id,
        lemma=lemma,
        pos=pos,
        cefr_level=cefr_level,
        zipf_frequency=zipf_frequency,
        source_phrase=phrase(context_fragment, lemma, lemmas=_LEMMAS),
        occurrences=occurrences,
        status=CandidateStatus.PENDING,
        is_phrasal_verb=is_phrasal_verb,
        cefr_breakdown=cefr_breakdown,
        usage_distribution=usage_distribution,
    )


def _breakdown() -> CEFRBreakdown:
    vote = SourceVote(
        source_name="Oxford 5000",
        distribution={CEFRLevel.B1: 1.0},
        top_level=CEFRLevel.B1,
    )
    return CEFRBreakdown(
        final_level=CEFRLevel.B1,
        decision_method="priority",
        priority_votes=[vote],
        votes=[],
    )


def _mock_repo(candidate: StoredCandidate | None = None) -> MagicMock:
    repo = MagicMock()
    repo.get_by_id.return_value = candidate

    def _create(candidates: list[StoredCandidate]) -> list[StoredCandidate]:
        result = []
        for i, c in enumerate(candidates):
            c.id = 200 + i
            result.append(c)
        return result

    repo.create_batch.side_effect = _create
    return repo


def _make_use_case(
    candidate_repo: MagicMock | None = None,
    review_status: MagicMock | None = None,
) -> ReplaceWithExampleUseCase:
    reader = MagicMock()
    reader.read_for.side_effect = _read_for
    reader.read.side_effect = _read
    return ReplaceWithExampleUseCase(
        candidate_repo=candidate_repo or MagicMock(),
        review_status=review_status or MagicMock(),
        phrase_reader=reader,
    )


@pytest.mark.unit
class TestReplaceWithExampleGuards:
    def test_raises_not_found_when_candidate_missing(self) -> None:
        repo = MagicMock()
        repo.get_by_id.return_value = None
        use_case = _make_use_case(candidate_repo=repo)

        with pytest.raises(CandidateNotFoundError):
            use_case.execute(candidate_id=999, example_text="new phrase")

    def test_raises_value_error_when_example_text_empty(self) -> None:
        repo = _mock_repo(_candidate())
        use_case = _make_use_case(candidate_repo=repo)

        with pytest.raises(ValueError, match="example_text"):
            use_case.execute(candidate_id=1, example_text="")

    def test_raises_value_error_when_example_text_whitespace(self) -> None:
        repo = _mock_repo(_candidate())
        use_case = _make_use_case(candidate_repo=repo)

        with pytest.raises(ValueError, match="example_text"):
            use_case.execute(candidate_id=1, example_text="   ")

    def test_example_without_the_target_is_refused(self) -> None:
        repo = _mock_repo(_candidate())
        review_status = MagicMock()
        use_case = _make_use_case(candidate_repo=repo, review_status=review_status)

        with pytest.raises(TargetNotInPhraseError):
            use_case.execute(candidate_id=1, example_text="She walks every morning.")

        repo.update_status.assert_not_called()
        repo.create_batch.assert_not_called()
        review_status.refresh.assert_not_called()


@pytest.mark.unit
class TestReplaceWithExampleHappyPath:
    def test_refreshes_the_source_review_status(self) -> None:
        review_status = MagicMock()
        use_case = _make_use_case(
            candidate_repo=_mock_repo(_candidate()), review_status=review_status,
        )

        use_case.execute(candidate_id=1, example_text="She runs every morning.")

        review_status.refresh.assert_called_once_with(10)

    def test_skips_old_candidate(self) -> None:
        original = _candidate()
        repo = _mock_repo(original)
        use_case = _make_use_case(candidate_repo=repo)

        use_case.execute(candidate_id=1, example_text="She runs every morning.")

        repo.update_status.assert_called_once_with(1, CandidateStatus.SKIP)

    def test_creates_new_candidate_with_correct_fields(self) -> None:
        original = _candidate(
            candidate_id=1,
            source_id=10,
            lemma="run",
            pos="VERB",
            cefr_level="B1",
            zipf_frequency=4.0,
            is_phrasal_verb=False,
        )
        repo = _mock_repo(original)
        use_case = _make_use_case(candidate_repo=repo)

        use_case.execute(candidate_id=1, example_text="She runs every morning.")

        created = repo.create_batch.call_args[0][0][0]
        assert created.source_id == 10
        assert created.lemma == "run"
        assert created.pos == "VERB"
        assert created.cefr_level == "B1"
        assert created.zipf_frequency == 4.0
        assert created.is_sweet_spot is True
        assert created.is_phrasal_verb is False
        assert created.source_phrase.text == "She runs every morning."
        assert created.source_phrase.target_text() == "runs"
        assert created.polished_phrase is None
        assert created.phrase_position is None
        assert created.occurrences == 1
        assert created.status == CandidateStatus.PENDING

    def test_returns_dto_with_new_candidate(self) -> None:
        repo = _mock_repo(_candidate())
        use_case = _make_use_case(candidate_repo=repo)

        result = use_case.execute(candidate_id=1, example_text="She runs every morning.")

        assert result.id == 200
        assert result.phrase.text == "She runs every morning."
        assert result.phrase.target == [1]
        assert result.phrase_position is None
        assert result.status == CandidateStatus.PENDING.value

    def test_strips_markdown_bold_from_example(self) -> None:
        repo = _mock_repo(_candidate())
        use_case = _make_use_case(candidate_repo=repo)

        use_case.execute(
            candidate_id=1,
            example_text="She **runs** every morning.",
        )

        created = repo.create_batch.call_args[0][0][0]
        assert created.source_phrase.text == "She runs every morning."
        assert created.source_phrase.target_text() == "runs"

    def test_bold_words_are_the_target(self) -> None:
        """The bold run wins over the first match of the card's lemma."""
        repo = _mock_repo(_candidate())
        use_case = _make_use_case(candidate_repo=repo)

        use_case.execute(
            candidate_id=1,
            example_text="Run fast, she **runs** every morning.",
        )

        created = repo.create_batch.call_args[0][0][0]
        assert created.source_phrase.text == "Run fast, she runs every morning."
        assert created.source_phrase.target == (3,)

    def test_new_candidate_keeps_cefr_breakdown_and_usage(self) -> None:
        """The level is derived from the breakdown on load, so a replacement
        without it would come back from the DB with no CEFR level."""
        breakdown = _breakdown()
        usage = UsageDistribution(groups={"informal": 1.0})
        repo = _mock_repo(_candidate(cefr_breakdown=breakdown, usage_distribution=usage))
        use_case = _make_use_case(candidate_repo=repo)

        result = use_case.execute(candidate_id=1, example_text="She runs every morning.")

        created = repo.create_batch.call_args[0][0][0]
        assert created.cefr_breakdown == breakdown
        assert created.usage_distribution == usage
        assert result.cefr_breakdown is not None
        assert result.usage_distribution == {"informal": 1.0}
