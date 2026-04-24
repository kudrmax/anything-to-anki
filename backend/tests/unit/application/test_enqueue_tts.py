from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from backend.application.use_cases.enqueue_tts_generation import (
    EnqueueTTSGenerationUseCase,
)
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.job_type import JobType


def _make_candidate(candidate_id: int, source_id: int = 10) -> StoredCandidate:
    return StoredCandidate(
        id=candidate_id,
        source_id=source_id,
        lemma=f"word_{candidate_id}",
        pos="NOUN",
        status=CandidateStatus.PENDING,
        context_fragment=f"Context for word_{candidate_id}.",
        cefr_level=None,
        zipf_frequency=4.0,
        fragment_purity="clean",
        occurrences=1,
    )


@pytest.mark.unit
def test_enqueue_creates_tts_jobs() -> None:
    tts_repo = MagicMock()
    tts_repo.get_eligible_candidate_ids.return_value = [1, 2, 3]

    candidate_repo = MagicMock()
    candidate_repo.get_by_ids.return_value = [
        _make_candidate(1), _make_candidate(2), _make_candidate(3),
    ]

    settings_repo = MagicMock()
    settings_repo.get.return_value = None

    job_repo = MagicMock()

    use_case = EnqueueTTSGenerationUseCase(
        tts_repo=tts_repo,
        candidate_repo=candidate_repo,
        settings_repo=settings_repo,
        job_repo=job_repo,
    )
    result = use_case.execute(source_id=10)

    assert len(result) == 3
    job_repo.create_bulk.assert_called_once()
    jobs = job_repo.create_bulk.call_args[0][0]
    assert all(j.job_type == JobType.TTS for j in jobs)
    assert all(j.source_id == 10 for j in jobs)


@pytest.mark.unit
def test_enqueue_returns_empty_when_no_eligible() -> None:
    tts_repo = MagicMock()
    tts_repo.get_eligible_candidate_ids.return_value = []

    use_case = EnqueueTTSGenerationUseCase(
        tts_repo=tts_repo,
        candidate_repo=MagicMock(),
        settings_repo=MagicMock(),
        job_repo=MagicMock(),
    )
    result = use_case.execute(source_id=10)

    assert result == []


@pytest.mark.unit
def test_enqueue_jobs_have_correct_candidate_ids() -> None:
    """Each created job must reference the correct candidate_id."""
    tts_repo = MagicMock()
    tts_repo.get_eligible_candidate_ids.return_value = [5, 10, 15]

    candidate_repo = MagicMock()
    candidate_repo.get_by_ids.return_value = [
        _make_candidate(5, source_id=7),
        _make_candidate(10, source_id=7),
        _make_candidate(15, source_id=7),
    ]

    settings_repo = MagicMock()
    settings_repo.get.return_value = None

    job_repo = MagicMock()

    use_case = EnqueueTTSGenerationUseCase(
        tts_repo=tts_repo,
        candidate_repo=candidate_repo,
        settings_repo=settings_repo,
        job_repo=job_repo,
    )
    result = use_case.execute(source_id=7)

    jobs = job_repo.create_bulk.call_args[0][0]
    job_candidate_ids = {j.candidate_id for j in jobs}
    assert job_candidate_ids == {5, 10, 15}
    assert all(j.source_id == 7 for j in jobs)


@pytest.mark.unit
def test_enqueue_calls_sort_by_relevance() -> None:
    """sort_by_relevance must be called to order candidates."""
    tts_repo = MagicMock()
    tts_repo.get_eligible_candidate_ids.return_value = [1, 2]

    candidates = [_make_candidate(1), _make_candidate(2)]
    candidate_repo = MagicMock()
    candidate_repo.get_by_ids.return_value = candidates

    settings_repo = MagicMock()
    settings_repo.get.return_value = None

    job_repo = MagicMock()

    use_case = EnqueueTTSGenerationUseCase(
        tts_repo=tts_repo,
        candidate_repo=candidate_repo,
        settings_repo=settings_repo,
        job_repo=job_repo,
    )

    with patch(
        "backend.domain.services.candidate_sorting.sort_by_relevance",
        return_value=candidates,
    ) as mock_sort:
        use_case.execute(source_id=10)

        mock_sort.assert_called_once()
        call_args = mock_sort.call_args
        # First positional arg is the candidates list
        assert len(call_args[0]) >= 1


@pytest.mark.unit
def test_enqueue_respects_usage_group_order_from_settings() -> None:
    """When usage_group_order setting exists, it's passed to sort_by_relevance."""
    tts_repo = MagicMock()
    tts_repo.get_eligible_candidate_ids.return_value = [1]

    candidates = [_make_candidate(1)]
    candidate_repo = MagicMock()
    candidate_repo.get_by_ids.return_value = candidates

    settings_repo = MagicMock()
    settings_repo.get.side_effect = lambda key, *a: (
        '["rare", "common"]' if key == "usage_group_order" else None
    )

    job_repo = MagicMock()

    use_case = EnqueueTTSGenerationUseCase(
        tts_repo=tts_repo,
        candidate_repo=candidate_repo,
        settings_repo=settings_repo,
        job_repo=job_repo,
    )

    with patch(
        "backend.domain.services.candidate_sorting.sort_by_relevance",
        return_value=candidates,
    ) as mock_sort:
        use_case.execute(source_id=10)

        mock_sort.assert_called_once()
        assert mock_sort.call_args.kwargs["usage_order"] == ["rare", "common"]
