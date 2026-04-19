"""Tests for ReplaceWithExampleUseCase."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.candidate_status import CandidateStatus


def _candidate(
    *,
    candidate_id: int = 1,
    source_id: int = 10,
    lemma: str = "run",
    pos: str = "VERB",
    cefr_level: str | None = "B1",
    zipf_frequency: float = 4.0,
    context_fragment: str = "He ran to the store.",
    fragment_purity: str = "clean",
    occurrences: int = 2,
    is_phrasal_verb: bool = False,
    surface_form: str | None = "ran",
) -> StoredCandidate:
    return StoredCandidate(
        id=candidate_id,
        source_id=source_id,
        lemma=lemma,
        pos=pos,
        cefr_level=cefr_level,
        zipf_frequency=zipf_frequency,
        context_fragment=context_fragment,
        fragment_purity=fragment_purity,
        occurrences=occurrences,
        status=CandidateStatus.PENDING,
        surface_form=surface_form,
        is_phrasal_verb=is_phrasal_verb,
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
) -> ReplaceWithExampleUseCase:
    return ReplaceWithExampleUseCase(
        candidate_repo=candidate_repo or MagicMock(),
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


@pytest.mark.unit
class TestReplaceWithExampleHappyPath:
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
            fragment_purity="clean",
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
        assert created.fragment_purity == "clean"
        assert created.context_fragment == "She runs every morning."
        assert created.has_custom_context_fragment is True
        assert created.surface_form is None
        assert created.occurrences == 1
        assert created.status == CandidateStatus.PENDING

    def test_returns_dto_with_new_candidate(self) -> None:
        repo = _mock_repo(_candidate())
        use_case = _make_use_case(candidate_repo=repo)

        result = use_case.execute(candidate_id=1, example_text="She runs every morning.")

        assert result.id == 200
        assert result.context_fragment == "She runs every morning."
        assert result.has_custom_context_fragment is True
        assert result.status == CandidateStatus.PENDING.value

    def test_strips_markdown_bold_from_example(self) -> None:
        repo = _mock_repo(_candidate())
        use_case = _make_use_case(candidate_repo=repo)

        use_case.execute(
            candidate_id=1,
            example_text="She **runs** every morning.",
        )

        created = repo.create_batch.call_args[0][0][0]
        assert created.context_fragment == "She runs every morning."
