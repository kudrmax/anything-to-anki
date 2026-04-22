"""Tests for JobWorker — SQLite-backed async job worker."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest

from backend.domain.entities.job import Job
from backend.domain.exceptions import CancelledByUserError, PermanentAIError, PermanentMediaError
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.infrastructure.queue.job_worker import JobWorker

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _make_job(
    *,
    job_type: JobType = JobType.MEDIA,
    status: JobStatus = JobStatus.RUNNING,
    candidate_id: int | None = 1,
    job_id: int = 100,
    source_id: int = 10,
) -> Job:
    return Job(
        id=job_id,
        job_type=job_type,
        candidate_id=candidate_id,
        source_id=source_id,
        status=status,
        error=None,
        created_at=NOW,
        started_at=NOW,
    )


class _FakeSession:
    """Minimal session stub for context manager."""
    pass


@contextmanager
def _mock_session_scope() -> Generator[_FakeSession, None, None]:
    yield _FakeSession()


def _make_container() -> MagicMock:
    container = MagicMock()
    container.session_scope = _mock_session_scope
    return container


@pytest.mark.unit
class TestReconcileOnStartup:

    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    def test_reconcile_resets_running_jobs(self, mock_repo_cls: MagicMock) -> None:
        repo_instance = MagicMock()
        repo_instance.fail_all_running.return_value = 3
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        worker._reconcile_on_startup()

        repo_instance.fail_all_running.assert_called_once_with(
            "interrupted by worker restart",
        )

    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    def test_reconcile_no_running_jobs(self, mock_repo_cls: MagicMock) -> None:
        repo_instance = MagicMock()
        repo_instance.fail_all_running.return_value = 0
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        worker._reconcile_on_startup()

        repo_instance.fail_all_running.assert_called_once()


@pytest.mark.unit
class TestProcessOneJob:

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_returns_false_when_queue_empty(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        repo_instance = MagicMock()
        repo_instance.dequeue_next.return_value = None
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        result = await worker._process_one_job()
        assert result is False

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_dispatches_media_job_and_deletes(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job = _make_job(job_type=JobType.MEDIA)
        repo_instance = MagicMock()
        repo_instance.dequeue_next.return_value = job
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        # Mock _handle_media to avoid real execution
        async def noop_media(*args: Any) -> None:
            pass

        worker._handle_media = noop_media  # type: ignore[assignment]

        result = await worker._process_one_job()
        assert result is True
        # On success, jobs are deleted
        repo_instance.delete_bulk.assert_called_once_with([job.id])

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_handles_cancelled_by_user_error(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job = _make_job(job_type=JobType.MEDIA)
        repo_instance = MagicMock()
        repo_instance.dequeue_next.return_value = job
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        async def raise_cancelled(*args: Any) -> None:
            raise CancelledByUserError("cancelled")

        worker._handle_media = raise_cancelled  # type: ignore[assignment]

        result = await worker._process_one_job()
        assert result is True
        # No mark_failed_bulk on cancellation
        repo_instance.mark_failed_bulk.assert_not_called()
        # No delete either
        repo_instance.delete_bulk.assert_not_called()

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_handles_permanent_media_error(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job = _make_job(job_type=JobType.MEDIA)
        repo_instance = MagicMock()
        repo_instance.dequeue_next.return_value = job
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        async def raise_permanent(*args: Any) -> None:
            raise PermanentMediaError("file corrupt")

        worker._handle_media = raise_permanent  # type: ignore[assignment]

        result = await worker._process_one_job()
        assert result is True
        repo_instance.mark_failed_bulk.assert_called_once_with(
            [job.id], "file corrupt",
        )

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_handles_generic_exception(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job = _make_job(job_type=JobType.MEDIA)
        repo_instance = MagicMock()
        repo_instance.dequeue_next.return_value = job
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        async def raise_generic(*args: Any) -> None:
            raise RuntimeError("something broke")

        worker._handle_media = raise_generic  # type: ignore[assignment]

        result = await worker._process_one_job()
        assert result is True
        repo_instance.mark_failed_bulk.assert_called_once_with(
            [job.id], "RuntimeError: something broke",
        )

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_dispatches_pronunciation_job(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job = _make_job(job_type=JobType.PRONUNCIATION)
        repo_instance = MagicMock()
        repo_instance.dequeue_next.return_value = job
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        async def noop_pron(*args: Any) -> None:
            pass

        worker._handle_pronunciation = noop_pron  # type: ignore[assignment]

        result = await worker._process_one_job()
        assert result is True
        repo_instance.delete_bulk.assert_called_once_with([job.id])

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_dispatches_video_download_job(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job = _make_job(job_type=JobType.VIDEO_DOWNLOAD, candidate_id=None)
        repo_instance = MagicMock()
        repo_instance.dequeue_next.return_value = job
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        async def noop_video(*args: Any) -> None:
            pass

        worker._handle_video_download = noop_video  # type: ignore[assignment]

        result = await worker._process_one_job()
        assert result is True
        repo_instance.delete_bulk.assert_called_once_with([job.id])


@pytest.mark.unit
class TestHandleMeaning:

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_meaning_batches_and_deletes_on_success(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        primary_job = _make_job(job_type=JobType.MEANING, job_id=1, candidate_id=10)
        extra_job = _make_job(job_type=JobType.MEANING, job_id=2, candidate_id=11)

        repo_instance = MagicMock()
        repo_instance.dequeue_batch.return_value = [extra_job]
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        # Mock _run_meaning_batch to do nothing
        worker._run_meaning_batch = MagicMock()  # type: ignore[assignment]

        await worker._handle_meaning(primary_job)

        # Both jobs should be deleted
        repo_instance.delete_bulk.assert_called_once()
        deleted_ids = repo_instance.delete_bulk.call_args[0][0]
        assert set(deleted_ids) == {1, 2}

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_meaning_batch_marks_failed_on_error(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        primary_job = _make_job(job_type=JobType.MEANING, job_id=1, candidate_id=10)

        repo_instance = MagicMock()
        repo_instance.dequeue_batch.return_value = []
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        def raise_error(*args: Any) -> None:
            raise RuntimeError("batch failed")

        worker._run_meaning_batch = raise_error  # type: ignore[assignment]

        await worker._handle_meaning(primary_job)

        repo_instance.mark_failed_bulk.assert_called_once()
        call_args = repo_instance.mark_failed_bulk.call_args
        assert 1 in call_args[0][0]
        assert "RuntimeError: batch failed" in call_args[0][1]

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_meaning_batch_timeout(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        primary_job = _make_job(job_type=JobType.MEANING, job_id=1, candidate_id=10)

        repo_instance = MagicMock()
        repo_instance.dequeue_batch.return_value = []
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        # Patch asyncio.wait_for to raise TimeoutError
        with patch("backend.infrastructure.queue.job_worker.asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = TimeoutError()
            await worker._handle_meaning(primary_job)

        repo_instance.mark_failed_bulk.assert_called_once()
        call_args = repo_instance.mark_failed_bulk.call_args
        assert call_args[0][1] == "timeout"

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_meaning_no_candidate_ids_deletes_jobs(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        """Jobs with candidate_id=None are cleaned up without processing."""
        primary_job = _make_job(
            job_type=JobType.MEANING, job_id=1, candidate_id=None,
        )

        repo_instance = MagicMock()
        repo_instance.dequeue_batch.return_value = []
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        await worker._handle_meaning(primary_job)

        # Jobs deleted without processing
        repo_instance.delete_bulk.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_meaning_permanent_ai_error(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        primary_job = _make_job(job_type=JobType.MEANING, job_id=1, candidate_id=10)
        extra_job = _make_job(job_type=JobType.MEANING, job_id=2, candidate_id=11)

        repo_instance = MagicMock()
        repo_instance.dequeue_batch.return_value = [extra_job]
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        def raise_perm(*args: Any) -> None:
            raise PermanentAIError("model unavailable")

        worker._run_meaning_batch = raise_perm  # type: ignore[assignment]

        await worker._handle_meaning(primary_job)

        repo_instance.mark_failed_bulk.assert_called_once()
        call_args = repo_instance.mark_failed_bulk.call_args
        assert set(call_args[0][0]) == {1, 2}
        assert call_args[0][1] == "model unavailable"


@pytest.mark.unit
class TestHelpers:

    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    def test_mark_jobs_failed_skips_none_ids(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job_with_id = _make_job(job_id=1)
        job_without_id = _make_job()
        # Simulate id=None by creating a new Job
        job_no_id = Job(
            id=None, job_type=JobType.MEDIA, candidate_id=1,
            source_id=10, status=JobStatus.RUNNING, error=None,
            created_at=NOW, started_at=NOW,
        )

        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        worker._mark_jobs_failed([job_with_id, job_no_id], "test error")

        repo_instance.mark_failed_bulk.assert_called_once_with([1], "test error")

    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    def test_mark_jobs_failed_empty_when_all_none(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job_no_id = Job(
            id=None, job_type=JobType.MEDIA, candidate_id=1,
            source_id=10, status=JobStatus.RUNNING, error=None,
            created_at=NOW, started_at=NOW,
        )

        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        worker._mark_jobs_failed([job_no_id], "test error")

        # Should not call mark_failed_bulk when no valid ids
        repo_instance.mark_failed_bulk.assert_not_called()

    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    def test_delete_jobs_skips_none_ids(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        job_no_id = Job(
            id=None, job_type=JobType.MEDIA, candidate_id=1,
            source_id=10, status=JobStatus.RUNNING, error=None,
            created_at=NOW, started_at=NOW,
        )

        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        worker._delete_jobs([job_no_id])

        repo_instance.delete_bulk.assert_not_called()


@pytest.mark.unit
class TestRunMeaningBatch:
    """Tests for the sync _run_meaning_batch method."""

    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    @patch("backend.infrastructure.queue.cancellation_token.CancellationToken", autospec=True)
    def test_calls_execute_batch_with_candidate_ids(
        self, mock_token_cls: MagicMock, mock_repo_cls: MagicMock,
    ) -> None:
        mock_token = MagicMock()
        mock_token_cls.return_value = mock_token

        container = _make_container()
        use_case = MagicMock()
        container.meaning_generation_use_case.return_value = use_case

        # Patch the local import of CancellationToken inside _run_meaning_batch
        worker = JobWorker(container)
        primary_job = _make_job(job_type=JobType.MEANING, job_id=1, candidate_id=10)

        with patch(
            "backend.infrastructure.queue.cancellation_token.CancellationToken",
            return_value=mock_token,
        ):
            worker._run_meaning_batch([10, 11, 12], primary_job)

        use_case.execute_batch.assert_called_once_with([10, 11, 12])

    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    def test_raises_cancelled_when_token_cancelled(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        mock_token = MagicMock()
        mock_token.check.side_effect = CancelledByUserError(1)

        container = _make_container()
        worker = JobWorker(container)
        primary_job = _make_job(job_type=JobType.MEANING, job_id=1, candidate_id=10)

        with patch(
            "backend.infrastructure.queue.cancellation_token.CancellationToken",
            return_value=mock_token,
        ), pytest.raises(CancelledByUserError):
            worker._run_meaning_batch([10], primary_job)


@pytest.mark.unit
class TestRunMedia:
    """Tests for the sync _run_media method."""

    def test_calls_media_extraction_use_case(self) -> None:
        container = _make_container()
        use_case = MagicMock()
        container.media_extraction_use_case.return_value = use_case

        with patch(
            "backend.infrastructure.persistence.sqla_candidate_repository.SqlaCandidateRepository",
        ) as mock_cand_repo_cls:
            mock_cand_repo_cls.return_value.get_by_id.return_value = None

            worker = JobWorker(container)
            job = _make_job(job_type=JobType.MEDIA, candidate_id=42)
            worker._run_media(job)

        use_case.execute_one.assert_called_once_with(42)

    def test_runs_cleanup_when_candidate_found(self) -> None:
        container = _make_container()
        use_case = MagicMock()
        container.media_extraction_use_case.return_value = use_case
        cleanup = MagicMock()
        container.cleanup_youtube_video_use_case.return_value = cleanup

        fake_candidate = MagicMock()
        fake_candidate.source_id = 5

        with patch(
            "backend.infrastructure.persistence.sqla_candidate_repository.SqlaCandidateRepository",
        ) as mock_cand_repo_cls:
            mock_cand_repo_cls.return_value.get_by_id.return_value = fake_candidate

            worker = JobWorker(container)
            job = _make_job(job_type=JobType.MEDIA, candidate_id=42)
            worker._run_media(job)

        cleanup.execute.assert_called_once_with(5)


@pytest.mark.unit
class TestRunPronunciation:
    """Tests for the sync _run_pronunciation method."""

    def test_calls_download_pronunciation_use_case(self) -> None:
        container = _make_container()
        use_case = MagicMock()
        container.download_pronunciation_use_case.return_value = use_case

        worker = JobWorker(container)
        job = _make_job(job_type=JobType.PRONUNCIATION, candidate_id=42)
        worker._run_pronunciation(job)

        use_case.execute_one.assert_called_once_with(42)


@pytest.mark.unit
class TestHandleMedia:
    """Tests for _handle_media async method."""

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_media_timeout_marks_failed(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        job = _make_job(job_type=JobType.MEDIA, job_id=1)

        with patch("backend.infrastructure.queue.job_worker.asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = TimeoutError()
            await worker._handle_media(job)

        repo_instance.mark_failed_bulk.assert_called_once_with([1], "timeout")

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_media_success_deletes_job(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        job = _make_job(job_type=JobType.MEDIA, job_id=1)

        with patch("backend.infrastructure.queue.job_worker.asyncio.wait_for"):
            await worker._handle_media(job)

        repo_instance.delete_bulk.assert_called_once_with([1])


@pytest.mark.unit
class TestHandlePronunciation:
    """Tests for _handle_pronunciation async method."""

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_pronunciation_timeout_marks_failed(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        job = _make_job(job_type=JobType.PRONUNCIATION, job_id=1)

        with patch("backend.infrastructure.queue.job_worker.asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = TimeoutError()
            await worker._handle_pronunciation(job)

        repo_instance.mark_failed_bulk.assert_called_once_with([1], "timeout")

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_pronunciation_success_deletes_job(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)
        job = _make_job(job_type=JobType.PRONUNCIATION, job_id=1)

        with patch("backend.infrastructure.queue.job_worker.asyncio.wait_for"):
            await worker._handle_pronunciation(job)

        repo_instance.delete_bulk.assert_called_once_with([1])


@pytest.mark.unit
class TestHandleVideoDownload:
    """Tests for _handle_video_download async method."""

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_success_deletes_job(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        use_case = MagicMock()
        container.download_video_use_case.return_value = use_case

        worker = JobWorker(container)
        job = _make_job(job_type=JobType.VIDEO_DOWNLOAD, job_id=1, candidate_id=None)
        await worker._handle_video_download(job)

        use_case.execute.assert_called_once_with(10)  # source_id
        repo_instance.delete_bulk.assert_called_once_with([1])

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_error_updates_source_status_and_reraises(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        repo_instance = MagicMock()
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        use_case = MagicMock()
        use_case.execute.side_effect = RuntimeError("download failed")
        container.download_video_use_case.return_value = use_case

        with patch(
            "backend.infrastructure.persistence.sqla_source_repository.SqlaSourceRepository",
        ) as mock_source_repo_cls:
            source_repo = MagicMock()
            mock_source_repo_cls.return_value = source_repo

            worker = JobWorker(container)
            job = _make_job(job_type=JobType.VIDEO_DOWNLOAD, job_id=1, candidate_id=None)

            with pytest.raises(RuntimeError, match="download failed"):
                await worker._handle_video_download(job)

            source_repo.update_status.assert_called_once()


@pytest.mark.unit
class TestRunLoop:
    """Tests for the run() main loop."""

    @pytest.mark.asyncio
    @patch("backend.infrastructure.queue.job_worker.SqlaJobRepository")
    async def test_run_processes_until_shutdown(
        self, mock_repo_cls: MagicMock,
    ) -> None:
        repo_instance = MagicMock()
        repo_instance.fail_all_running.return_value = 0
        repo_instance.dequeue_next.return_value = None
        mock_repo_cls.return_value = repo_instance

        container = _make_container()
        worker = JobWorker(container)

        # Shutdown after first poll
        original_sleep = asyncio.sleep

        async def shutdown_on_sleep(delay: float) -> None:
            worker._shutdown = True

        with patch("backend.infrastructure.queue.job_worker.asyncio.sleep", shutdown_on_sleep):
            with patch("backend.infrastructure.queue.job_worker.asyncio.get_running_loop") as mock_loop:
                mock_loop.return_value = MagicMock()
                await worker.run()

        repo_instance.fail_all_running.assert_called_once()
        repo_instance.dequeue_next.assert_called_once()


@pytest.mark.unit
class TestRequestShutdown:

    def test_request_shutdown_sets_flag(self) -> None:
        container = _make_container()
        worker = JobWorker(container)
        assert worker._shutdown is False
        worker._request_shutdown()
        assert worker._shutdown is True
