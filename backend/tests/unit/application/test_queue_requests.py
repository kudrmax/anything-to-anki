"""Use cases that put work into the queue or act on it on the user's behalf."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.enqueue_candidate_tts import EnqueueCandidateTTSUseCase
from backend.application.use_cases.manage_queue import ManageQueueUseCase
from backend.application.use_cases.request_video_download import RequestVideoDownloadUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    CandidateNotFoundError,
    SourceHasNoUrlError,
    SourceNotFoundError,
    VideoAlreadyDownloadedError,
)
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.job_selection import JobSelection
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_status import SourceStatus

SOURCE_ID = 42


def _youtube_source(source_url: str | None = "https://youtube.com/watch?v=abc") -> Source:
    return Source(
        raw_text="subtitles",
        status=SourceStatus.DONE,
        input_method=InputMethod.YOUTUBE_URL,
        content_type=ContentType.VIDEO,
        source_url=source_url,
        id=SOURCE_ID,
    )


def _queued(job_repo: MagicMock) -> list[tuple[JobType, int, int | None]]:
    (jobs,), _ = job_repo.enqueue.call_args
    return [(j.job_type, j.source_id, j.candidate_id) for j in jobs]


@pytest.mark.unit
class TestRequestVideoDownload:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.job_repo = MagicMock()
        self.use_case = RequestVideoDownloadUseCase(self.source_repo, self.job_repo)

    def test_queues_one_source_level_job(self) -> None:
        self.source_repo.get_by_id.return_value = _youtube_source()

        self.use_case.execute(SOURCE_ID)

        assert _queued(self.job_repo) == [(JobType.VIDEO_DOWNLOAD, SOURCE_ID, None)]

    @pytest.mark.parametrize(("source", "error"), [
        (None, SourceNotFoundError),
        (_youtube_source(source_url=None), SourceHasNoUrlError),
    ])
    def test_rejects_sources_without_a_video_to_download(
        self, source: Source | None, error: type[Exception],
    ) -> None:
        self.source_repo.get_by_id.return_value = source

        with pytest.raises(error):
            self.use_case.execute(SOURCE_ID)
        self.job_repo.enqueue.assert_not_called()

    def test_rejects_already_downloaded_video(self) -> None:
        source = _youtube_source()
        source.video_path = "existing.mp4"
        self.source_repo.get_by_id.return_value = source

        with pytest.raises(VideoAlreadyDownloadedError):
            self.use_case.execute(SOURCE_ID)
        self.job_repo.enqueue.assert_not_called()


@pytest.mark.unit
class TestEnqueueCandidateTTS:
    def test_queues_tts_for_the_card(self) -> None:
        candidate_repo, job_repo = MagicMock(), MagicMock()
        candidate_repo.get_by_id.return_value = MagicMock(source_id=SOURCE_ID)

        EnqueueCandidateTTSUseCase(candidate_repo, job_repo).execute(7)

        assert _queued(job_repo) == [(JobType.TTS, SOURCE_ID, 7)]

    def test_missing_card(self) -> None:
        candidate_repo, job_repo = MagicMock(), MagicMock()
        candidate_repo.get_by_id.return_value = None

        with pytest.raises(CandidateNotFoundError):
            EnqueueCandidateTTSUseCase(candidate_repo, job_repo).execute(7)


@pytest.mark.unit
@pytest.mark.parametrize("action", ["cancel", "retry", "dismiss"])
def test_manage_queue_applies_the_action_to_the_selection(action: str) -> None:
    job_repo = MagicMock()
    getattr(job_repo, action).return_value = 4
    selection = JobSelection(job_type=JobType.MEANING, source_id=SOURCE_ID)

    affected = getattr(ManageQueueUseCase(job_repo), action)(selection)

    assert affected == 4
    getattr(job_repo, action).assert_called_once_with(selection)
