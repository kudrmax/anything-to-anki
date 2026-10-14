"""Use cases that put work into the queue or act on it on the user's behalf."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.enqueue_phrase_tts import EnqueuePhraseTTSUseCase
from backend.application.use_cases.manage_queue import ManageQueueUseCase
from backend.application.use_cases.request_video_download import RequestVideoDownloadUseCase
from backend.application.utils.requested_cards import RequestedCards
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    PhraseNotFoundError,
    SourceHasNoUrlError,
    SourceNotFoundError,
    SourceOperationBusyError,
    VideoAlreadyDownloadedError,
)
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.job_selection import JobSelection
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus

from tests.phrase_support import make_occurrence

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import Occurrence

SOURCE_ID = 42


def _youtube_source(source_url: str | None = "https://youtube.com/watch?v=abc") -> Source:
    return Source(
        status=SourceStatus.DONE,
        source_url=source_url,
        id=SOURCE_ID, format=Format.YOUTUBE, kind=Kind.SUBTITLES,
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


def _requested(
    phrase: Occurrence | None, busy_with: SourceOperationKind | None = None,
) -> RequestedCards:
    occurrence_repo, candidate_repo, lock = MagicMock(), MagicMock(), MagicMock()
    occurrence_repo.get.return_value = phrase
    candidate_repo.get_by_id.return_value = MagicMock(id=3, source_id=SOURCE_ID)
    lock.held.return_value = busy_with
    return RequestedCards(candidate_repo, occurrence_repo, lock)


def _shown_phrase() -> Occurrence:
    return replace(make_occurrence(candidate_id=3), id=7, revision=2)


@pytest.mark.unit
class TestEnqueuePhraseTTS:
    def test_queues_tts_for_the_phrase(self) -> None:
        job_repo = MagicMock()

        EnqueuePhraseTTSUseCase(_requested(_shown_phrase()), job_repo).execute(7)

        [job] = job_repo.enqueue.call_args.args[0]
        assert (job.job_type, job.source_id, job.candidate_id) == (JobType.TTS, SOURCE_ID, 3)
        assert (job.phrase_id, job.phrase_revision) == (7, 2)

    def test_missing_phrase(self) -> None:
        with pytest.raises(PhraseNotFoundError):
            EnqueuePhraseTTSUseCase(_requested(None), MagicMock()).execute(7)

    def test_busy_source(self) -> None:
        job_repo = MagicMock()
        cards = _requested(_shown_phrase(), busy_with=SourceOperationKind.REBUILD)

        with pytest.raises(SourceOperationBusyError):
            EnqueuePhraseTTSUseCase(cards, job_repo).execute(7)
        job_repo.enqueue.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize("action", ["cancel", "retry", "dismiss"])
def test_manage_queue_applies_the_action_to_the_selection(action: str) -> None:
    job_repo = MagicMock()
    getattr(job_repo, action).return_value = 4
    selection = JobSelection(job_type=JobType.MEANING, source_id=SOURCE_ID)

    affected = getattr(ManageQueueUseCase(job_repo), action)(selection)

    assert affected == 4
    getattr(job_repo, action).assert_called_once_with(selection)
