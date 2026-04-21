"""Unit tests for RetryQueueUseCase."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.retry_queue import RetryQueueUseCase
from backend.domain.value_objects.failed_error_group import FailedErrorGroup, SourceErrorCount


def _group(candidate_ids: list[int]) -> FailedErrorGroup:
    return FailedErrorGroup(
        error_text="some error",
        count=len(candidate_ids),
        source_counts=[],
        candidate_ids=candidate_ids,
    )


def _make_use_case(
    meaning_repo: MagicMock | None = None,
    media_repo: MagicMock | None = None,
    pronunciation_repo: MagicMock | None = None,
) -> RetryQueueUseCase:
    return RetryQueueUseCase(
        meaning_repo=meaning_repo or MagicMock(),
        media_repo=media_repo or MagicMock(),
        pronunciation_repo=pronunciation_repo or MagicMock(),
    )


@pytest.mark.unit
class TestRetryQueueUseCase:
    def test_retry_meanings_uses_meaning_repo(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = [_group([1, 2, 3])]
        use_case = _make_use_case(meaning_repo=meaning_repo)

        count = use_case.execute(job_type="meanings")

        meaning_repo.mark_queued_bulk.assert_called_once_with([1, 2, 3])
        assert count == 3

    def test_retry_media_uses_media_repo(self) -> None:
        media_repo = MagicMock()
        media_repo.get_failed_grouped_by_error.return_value = [_group([4, 5])]
        use_case = _make_use_case(media_repo=media_repo)

        count = use_case.execute(job_type="media")

        media_repo.mark_queued_bulk.assert_called_once_with([4, 5])
        assert count == 2

    def test_retry_pronunciation_uses_pronunciation_repo(self) -> None:
        pronunciation_repo = MagicMock()
        pronunciation_repo.get_failed_grouped_by_error.return_value = [_group([7])]
        use_case = _make_use_case(pronunciation_repo=pronunciation_repo)

        count = use_case.execute(job_type="pronunciation")

        pronunciation_repo.mark_queued_bulk.assert_called_once_with([7])
        assert count == 1

    def test_with_error_text_uses_get_candidate_ids_by_error(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_by_error.return_value = [10, 20]
        use_case = _make_use_case(meaning_repo=meaning_repo)

        count = use_case.execute(job_type="meanings", error_text="timeout")

        meaning_repo.get_candidate_ids_by_error.assert_called_once_with(
            "timeout", source_id=None
        )
        meaning_repo.mark_queued_bulk.assert_called_once_with([10, 20])
        assert count == 2

    def test_with_error_text_and_source_id(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_candidate_ids_by_error.return_value = [5]
        use_case = _make_use_case(meaning_repo=meaning_repo)

        count = use_case.execute(job_type="meanings", source_id=42, error_text="err")

        meaning_repo.get_candidate_ids_by_error.assert_called_once_with(
            "err", source_id=42
        )
        assert count == 1

    def test_without_error_text_collects_all_from_groups(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = [
            _group([1, 2]),
            _group([3, 4, 5]),
        ]
        use_case = _make_use_case(meaning_repo=meaning_repo)

        count = use_case.execute(job_type="meanings")

        call_ids = meaning_repo.mark_queued_bulk.call_args[0][0]
        assert set(call_ids) == {1, 2, 3, 4, 5}
        assert count == 5

    def test_passes_source_id_to_get_failed_grouped(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = []
        use_case = _make_use_case(meaning_repo=meaning_repo)

        use_case.execute(job_type="meanings", source_id=99)

        meaning_repo.get_failed_grouped_by_error.assert_called_once_with(source_id=99)

    def test_returns_zero_when_nothing_to_retry(self) -> None:
        meaning_repo = MagicMock()
        meaning_repo.get_failed_grouped_by_error.return_value = []
        use_case = _make_use_case(meaning_repo=meaning_repo)

        count = use_case.execute(job_type="meanings")

        meaning_repo.mark_queued_bulk.assert_not_called()
        assert count == 0

    def test_invalid_job_type_raises_value_error(self) -> None:
        use_case = _make_use_case()
        with pytest.raises(ValueError, match="Unknown job_type"):
            use_case.execute(job_type="unknown_type")
