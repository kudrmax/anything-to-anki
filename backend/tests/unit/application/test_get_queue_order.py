"""Unit tests for GetQueueOrderUseCase."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.application.use_cases.get_queue_order import GetQueueOrderUseCase
from backend.domain.value_objects.queued_job_info import QueuedJobInfo


def _job(
    job_id: str,
    job_type: str,
    source_id: int,
    position: int | None,
) -> QueuedJobInfo:
    return QueuedJobInfo(
        job_id=job_id,
        job_type=job_type,
        source_id=source_id,
        position=position,
        scheduled_at=1000.0,
    )


def _make_use_case(
    inspector: AsyncMock | None = None,
    source_repo: MagicMock | None = None,
) -> GetQueueOrderUseCase:
    return GetQueueOrderUseCase(
        inspector=inspector or AsyncMock(),
        source_repo=source_repo or MagicMock(),
    )


@pytest.mark.unit
class TestGetQueueOrderUseCase:
    @pytest.mark.asyncio
    async def test_combines_running_and_queued_jobs(self) -> None:
        inspector = AsyncMock()
        inspector.get_running_jobs.return_value = [
            _job("r1", "meanings", 10, None),
        ]
        inspector.get_queued_jobs.return_value = [
            _job("q1", "media", 20, 1),
            _job("q2", "meanings", 10, 2),
        ]
        inspector.get_total_queued.return_value = 2

        source_repo = MagicMock()
        source_repo.get_title_map.return_value = {10: "Source A", 20: "Source B"}

        use_case = _make_use_case(inspector, source_repo)
        result = await use_case.execute()

        assert len(result.running) == 1
        assert result.running[0].job_id == "r1"
        assert result.running[0].status == "running"
        assert result.running[0].source_title == "Source A"

        assert len(result.queued) == 2
        assert result.queued[0].job_id == "q1"
        assert result.queued[0].status == "queued"
        assert result.queued[0].source_title == "Source B"
        assert result.queued[1].source_title == "Source A"

        assert result.total_queued == 2

    @pytest.mark.asyncio
    async def test_empty_queues_return_empty_lists(self) -> None:
        inspector = AsyncMock()
        inspector.get_running_jobs.return_value = []
        inspector.get_queued_jobs.return_value = []
        inspector.get_total_queued.return_value = 0

        source_repo = MagicMock()
        source_repo.get_title_map.return_value = {}

        use_case = _make_use_case(inspector, source_repo)
        result = await use_case.execute()

        assert result.running == []
        assert result.queued == []
        assert result.total_queued == 0

    @pytest.mark.asyncio
    async def test_unknown_source_gets_empty_title(self) -> None:
        inspector = AsyncMock()
        inspector.get_running_jobs.return_value = [
            _job("r1", "meanings", 99, None),
        ]
        inspector.get_queued_jobs.return_value = []
        inspector.get_total_queued.return_value = 0

        source_repo = MagicMock()
        source_repo.get_title_map.return_value = {}  # source 99 not found

        use_case = _make_use_case(inspector, source_repo)
        result = await use_case.execute()

        assert result.running[0].source_title == ""

    @pytest.mark.asyncio
    async def test_passes_source_id_filter_to_inspector(self) -> None:
        inspector = AsyncMock()
        inspector.get_running_jobs.return_value = []
        inspector.get_queued_jobs.return_value = []
        inspector.get_total_queued.return_value = 0

        source_repo = MagicMock()
        source_repo.get_title_map.return_value = {}

        use_case = _make_use_case(inspector, source_repo)
        await use_case.execute(source_id=42)

        inspector.get_running_jobs.assert_called_once_with(source_id=42)
        inspector.get_queued_jobs.assert_called_once_with(source_id=42, limit=50)

    @pytest.mark.asyncio
    async def test_passes_limit_to_queued_jobs(self) -> None:
        inspector = AsyncMock()
        inspector.get_running_jobs.return_value = []
        inspector.get_queued_jobs.return_value = []
        inspector.get_total_queued.return_value = 0

        source_repo = MagicMock()
        source_repo.get_title_map.return_value = {}

        use_case = _make_use_case(inspector, source_repo)
        await use_case.execute(limit=100)

        inspector.get_queued_jobs.assert_called_once_with(source_id=None, limit=100)

    @pytest.mark.asyncio
    async def test_calls_get_title_map_with_all_source_ids(self) -> None:
        inspector = AsyncMock()
        inspector.get_running_jobs.return_value = [
            _job("r1", "meanings", 1, None),
        ]
        inspector.get_queued_jobs.return_value = [
            _job("q1", "media", 2, 1),
            _job("q2", "media", 1, 2),  # duplicate source_id
        ]
        inspector.get_total_queued.return_value = 2

        source_repo = MagicMock()
        source_repo.get_title_map.return_value = {1: "A", 2: "B"}

        use_case = _make_use_case(inspector, source_repo)
        await use_case.execute()

        call_args = source_repo.get_title_map.call_args[0][0]
        assert set(call_args) == {1, 2}  # deduplicated
