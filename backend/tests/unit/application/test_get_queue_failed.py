"""Unit tests for GetQueueFailedUseCase."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.get_queue_failed import GetQueueFailedUseCase
from backend.domain.value_objects.failed_error_group import FailedErrorGroup, SourceErrorCount


def _group(
    error_text: str,
    count: int,
    source_counts: list[SourceErrorCount] | None = None,
    candidate_ids: list[int] | None = None,
) -> FailedErrorGroup:
    return FailedErrorGroup(
        error_text=error_text,
        count=count,
        source_counts=source_counts or [],
        candidate_ids=candidate_ids or [],
    )


def _make_use_case(
    meaning_repo: MagicMock | None = None,
    media_repo: MagicMock | None = None,
    pronunciation_repo: MagicMock | None = None,
) -> GetQueueFailedUseCase:
    return GetQueueFailedUseCase(
        meaning_repo=meaning_repo or MagicMock(),
        media_repo=media_repo or MagicMock(),
        pronunciation_repo=pronunciation_repo or MagicMock(),
    )


@pytest.mark.unit
class TestGetQueueFailedUseCase:
    def test_empty_repos_return_empty_types(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = []
        media_repo = MagicMock()
        media_repo.get_failed_grouped_by_error.return_value = []
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_failed_grouped_by_error.return_value = []

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        result = use_case.execute()

        assert result.types == []

    def test_maps_failed_groups_for_each_repo(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = [
            _group("timeout", 3, candidate_ids=[1, 2, 3]),
        ]
        media_repo = MagicMock()
        media_repo.get_failed_grouped_by_error.return_value = [
            _group("ffmpeg error", 2, candidate_ids=[4, 5]),
        ]
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_failed_grouped_by_error.return_value = []

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        result = use_case.execute()

        assert len(result.types) == 2
        job_types = {t.job_type for t in result.types}
        assert job_types == {"meanings", "media"}

    def test_skips_job_types_with_no_failures(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = []
        media_repo = MagicMock()
        media_repo.get_failed_grouped_by_error.return_value = [
            _group("err", 1, candidate_ids=[99]),
        ]
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_failed_grouped_by_error.return_value = []

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        result = use_case.execute()

        assert len(result.types) == 1
        assert result.types[0].job_type == "media"

    def test_total_failed_sums_group_counts(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = [
            _group("err1", 4, candidate_ids=[1, 2, 3, 4]),
            _group("err2", 2, candidate_ids=[5, 6]),
        ]
        media_repo = MagicMock()
        media_repo.get_failed_grouped_by_error.return_value = []
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_failed_grouped_by_error.return_value = []

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        result = use_case.execute()

        assert result.types[0].total_failed == 6
        assert len(result.types[0].groups) == 2

    def test_maps_source_counts_to_failed_source_dtos(self) -> None:
        src_count = SourceErrorCount(source_id=10, source_title="Book", count=3)
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = [
            _group("err", 3, source_counts=[src_count], candidate_ids=[1, 2, 3]),
        ]
        media_repo = MagicMock()
        media_repo.get_failed_grouped_by_error.return_value = []
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_failed_grouped_by_error.return_value = []

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        result = use_case.execute()

        group = result.types[0].groups[0]
        assert len(group.sources) == 1
        assert group.sources[0].source_id == 10
        assert group.sources[0].source_title == "Book"
        assert group.sources[0].count == 3

    def test_passes_source_id_to_repos(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = []
        media_repo = MagicMock()
        media_repo.get_failed_grouped_by_error.return_value = []
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_failed_grouped_by_error.return_value = []

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        use_case.execute(source_id=77)

        meaning_repo.get_failed_grouped_by_error.assert_called_once_with(source_id=77)
        media_repo.get_failed_grouped_by_error.assert_called_once_with(source_id=77)
        pronunciation_repo.get_failed_grouped_by_error.assert_called_once_with(source_id=77)

    def test_candidate_ids_are_passed_through(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = [
            _group("err", 2, candidate_ids=[10, 20]),
        ]
        media_repo = MagicMock()
        media_repo.get_failed_grouped_by_error.return_value = []
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_failed_grouped_by_error.return_value = []

        use_case = _make_use_case(meaning_repo, media_repo, pronunciation_repo)
        result = use_case.execute()

        assert result.types[0].groups[0].candidate_ids == [10, 20]
