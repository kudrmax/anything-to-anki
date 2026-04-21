"""Unit tests for CancelQueueUseCase."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.use_cases.cancel_queue import CancelQueueUseCase


def _make_use_case(
    inspector: AsyncMock | None = None,
    meaning_repo: MagicMock | None = None,
    media_repo: MagicMock | None = None,
    pronunciation_repo: MagicMock | None = None,
) -> CancelQueueUseCase:
    return CancelQueueUseCase(
        inspector=inspector or AsyncMock(),
        meaning_repo=meaning_repo or MagicMock(),
        media_repo=media_repo or MagicMock(),
        pronunciation_repo=pronunciation_repo or MagicMock(),
    )


@pytest.mark.unit
class TestCancelQueueUseCase:
    @pytest.mark.asyncio
    async def test_cancel_single_job_by_id(self) -> None:
        inspector = AsyncMock()
        inspector.cancel_job.return_value = True
        use_case = _make_use_case(inspector=inspector)

        count = await use_case.execute(job_type="meanings", job_id="job-123")

        inspector.cancel_job.assert_called_once_with("job-123")
        inspector.cancel_jobs_by_type.assert_not_called()
        assert count == 1

    @pytest.mark.asyncio
    async def test_cancel_single_job_not_found_returns_zero(self) -> None:
        inspector = AsyncMock()
        inspector.cancel_job.return_value = False
        use_case = _make_use_case(inspector=inspector)

        count = await use_case.execute(job_type="meanings", job_id="missing-job")

        assert count == 0

    @pytest.mark.asyncio
    async def test_cancel_by_type_meanings_delegates_to_inspector(self) -> None:
        inspector = AsyncMock()
        inspector.cancel_jobs_by_type.return_value = 5
        use_case = _make_use_case(inspector=inspector)

        count = await use_case.execute(job_type="meanings")

        inspector.cancel_jobs_by_type.assert_called_once_with(
            "meanings", source_id=None
        )
        assert count == 5

    @pytest.mark.asyncio
    async def test_cancel_by_type_with_source_id(self) -> None:
        inspector = AsyncMock()
        inspector.cancel_jobs_by_type.return_value = 3
        use_case = _make_use_case(inspector=inspector)

        count = await use_case.execute(job_type="media", source_id=42)

        inspector.cancel_jobs_by_type.assert_called_once_with("media", source_id=42)
        assert count == 3

    @pytest.mark.asyncio
    async def test_cancel_by_type_does_not_call_cancel_job(self) -> None:
        inspector = AsyncMock()
        inspector.cancel_jobs_by_type.return_value = 2
        use_case = _make_use_case(inspector=inspector)

        await use_case.execute(job_type="pronunciation")

        inspector.cancel_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_job_type_raises_value_error(self) -> None:
        use_case = _make_use_case()
        with pytest.raises(ValueError, match="Unknown job_type"):
            await use_case.execute(job_type="bad_type")

    @pytest.mark.asyncio
    async def test_cancel_by_type_returns_inspector_count(self) -> None:
        inspector = AsyncMock()
        inspector.cancel_jobs_by_type.return_value = 0
        use_case = _make_use_case(inspector=inspector)

        count = await use_case.execute(job_type="meanings")

        assert count == 0
