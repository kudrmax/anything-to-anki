"""Use cases that put work into the queue or act on it on the user's behalf."""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.enqueue_phrase_meaning import EnqueuePhraseMeaningUseCase
from backend.application.use_cases.enqueue_phrase_tts import EnqueuePhraseTTSUseCase
from backend.application.use_cases.manage_queue import ManageQueueUseCase
from backend.application.use_cases.request_video_download import RequestVideoDownloadUseCase
from backend.application.utils.requested_cards import RequestedCards
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.collection import Collection
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
from backend.domain.value_objects.meaning_follow_up import MeaningFollowUp
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.queue.in_memory_generation_stops import InMemoryGenerationStops

from tests.phrase_support import make_occurrence
from tests.source_order_support import added_order

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


def _resolver(sources: list[Source], collection: int | None = None) -> SourceScopeResolver:
    source_repo, collection_repo = MagicMock(), MagicMock()
    source_repo.list_all.return_value = sources
    source_repo.get_by_id.side_effect = lambda source_id: next(
        (s for s in sources if s.id == source_id), None,
    )
    collection_repo.list_all.return_value = (
        [Collection(id=collection, name="Show")] if collection is not None else []
    )
    return SourceScopeResolver(source_repo, collection_repo, added_order())


def _downloads(resolver: SourceScopeResolver, job_repo: MagicMock) -> RequestVideoDownloadUseCase:
    return RequestVideoDownloadUseCase(resolver, job_repo, MagicMock())


def _jobs(downloading: frozenset[int] = frozenset()) -> MagicMock:
    job_repo = MagicMock()
    job_repo.has_active_jobs_for_source.side_effect = (
        lambda source_id, job_types: source_id in downloading
        and job_types == frozenset({JobType.VIDEO_DOWNLOAD})
    )
    return job_repo


@pytest.mark.unit
class TestRequestVideoDownload:
    def test_queues_one_source_level_job(self) -> None:
        job_repo = _jobs()
        use_case = _downloads(_resolver([_youtube_source()]), job_repo)

        assert use_case.execute(SourceScope.source(SOURCE_ID)) == 1

        assert _queued(job_repo) == [(JobType.VIDEO_DOWNLOAD, SOURCE_ID, None)]

    def test_downloads_every_missing_video_of_the_set(self) -> None:
        sources = [
            Source(id=1, status=SourceStatus.DONE, source_url="u1", collection_id=7),
            Source(
                id=2, status=SourceStatus.DONE, source_url="u2", video_path="v.mp4",
                collection_id=7,
            ),
            Source(id=3, status=SourceStatus.DONE, collection_id=7),
        ]
        job_repo = _jobs()
        use_case = _downloads(_resolver(sources, collection=7), job_repo)

        assert use_case.execute(SourceScope.collection(7)) == 1

        [[job]] = job_repo.enqueue.call_args.args
        assert job.source_id == 1

    def test_skips_a_source_whose_download_is_already_queued(self) -> None:
        sources = [
            Source(id=1, status=SourceStatus.DONE, source_url="u1", collection_id=7),
            Source(id=2, status=SourceStatus.DONE, source_url="u2", collection_id=7),
        ]
        job_repo = _jobs(downloading=frozenset({1}))
        use_case = _downloads(_resolver(sources, collection=7), job_repo)

        assert use_case.execute(SourceScope.collection(7)) == 1

        [[job]] = job_repo.enqueue.call_args.args
        assert job.source_id == 2

    def test_a_second_request_queues_nothing(self) -> None:
        job_repo = _jobs(downloading=frozenset({SOURCE_ID}))
        use_case = _downloads(_resolver([_youtube_source()]), job_repo)

        assert use_case.execute(SourceScope.source(SOURCE_ID)) == 0

        job_repo.enqueue.assert_not_called()

    def test_nothing_to_download_keeps_the_single_source_error(self) -> None:
        use_case = RequestVideoDownloadUseCase(
            _resolver([Source(id=3, status=SourceStatus.DONE)]), _jobs(),
            MagicMock(),
        )
        with pytest.raises(SourceHasNoUrlError):
            use_case.execute(SourceScope.source(3))

    def test_unknown_source(self) -> None:
        job_repo = _jobs()
        with pytest.raises(SourceNotFoundError):
            _downloads(_resolver([]), job_repo).execute(SourceScope.source(9))
        job_repo.enqueue.assert_not_called()

    def test_rejects_already_downloaded_video(self) -> None:
        source = _youtube_source()
        source.video_path = "existing.mp4"
        job_repo = _jobs()

        with pytest.raises(VideoAlreadyDownloadedError):
            _downloads(_resolver([source]), job_repo).execute(
                SourceScope.source(SOURCE_ID),
            )
        job_repo.enqueue.assert_not_called()


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

        EnqueuePhraseTTSUseCase(_requested(_shown_phrase()), job_repo, MagicMock()).execute(7)

        [job] = job_repo.enqueue.call_args.args[0]
        assert (job.job_type, job.source_id, job.candidate_id) == (JobType.TTS, SOURCE_ID, 3)
        assert (job.phrase_id, job.phrase_revision) == (7, 2)

    def test_missing_phrase(self) -> None:
        with pytest.raises(PhraseNotFoundError):
            EnqueuePhraseTTSUseCase(_requested(None), MagicMock(), MagicMock()).execute(7)

    def test_busy_source(self) -> None:
        job_repo = MagicMock()
        cards = _requested(_shown_phrase(), busy_with=SourceOperationKind.UPDATE)

        with pytest.raises(SourceOperationBusyError):
            EnqueuePhraseTTSUseCase(cards, job_repo, MagicMock()).execute(7)
        job_repo.enqueue.assert_not_called()


@pytest.mark.unit
class TestEnqueuePhraseMeaning:
    def test_queues_a_new_meaning_in_place_of_the_old_one(self) -> None:
        meaning_repo, job_repo = MagicMock(), MagicMock()

        EnqueuePhraseMeaningUseCase(
            _requested(_shown_phrase()), meaning_repo, job_repo, MagicMock(),
        ).execute(7)

        meaning_repo.delete_by_phrase_id.assert_called_once_with(7)
        [job] = job_repo.enqueue.call_args.args[0]
        assert (job.job_type, job.candidate_id, job.phrase_id, job.phrase_revision) == (
            JobType.MEANING, 3, 7, 2,
        )
        assert job.follow_up is None

    def test_queues_a_follow_up_with_its_question_keeping_the_meaning(self) -> None:
        meaning_repo, job_repo = MagicMock(), MagicMock()
        follow_up = MeaningFollowUp("free_question", "Is it formal?")

        EnqueuePhraseMeaningUseCase(
            _requested(_shown_phrase()), meaning_repo, job_repo, MagicMock(),
        ).execute(7, follow_up)

        meaning_repo.delete_by_phrase_id.assert_not_called()
        [job] = job_repo.enqueue.call_args.args[0]
        assert (job.job_type, job.follow_up) == (JobType.MEANING_FOLLOW_UP, follow_up)

    @pytest.mark.parametrize("follow_up", [
        MeaningFollowUp("sing_a_song"), MeaningFollowUp("free_question"),
    ])
    def test_a_follow_up_no_ai_call_can_answer_is_refused(
        self, follow_up: MeaningFollowUp,
    ) -> None:
        meaning_repo, job_repo = MagicMock(), MagicMock()
        use_case = EnqueuePhraseMeaningUseCase(
            _requested(_shown_phrase()), meaning_repo, job_repo, MagicMock(),
        )

        with pytest.raises(ValueError):
            use_case.execute(7, follow_up)
        meaning_repo.delete_by_phrase_id.assert_not_called()
        job_repo.enqueue.assert_not_called()

    def test_busy_source(self) -> None:
        job_repo = MagicMock()
        cards = _requested(_shown_phrase(), busy_with=SourceOperationKind.UPDATE)

        with pytest.raises(SourceOperationBusyError):
            EnqueuePhraseMeaningUseCase(cards, MagicMock(), job_repo, MagicMock()).execute(7)
        job_repo.enqueue.assert_not_called()


@pytest.mark.unit
@pytest.mark.parametrize("action", ["cancel", "retry", "dismiss"])
def test_manage_queue_applies_the_action_to_the_selection(action: str) -> None:
    job_repo = MagicMock()
    getattr(job_repo, action).return_value = 4
    selection = JobSelection(job_type=JobType.MEANING, source_id=SOURCE_ID)

    affected = getattr(
        ManageQueueUseCase(job_repo, MagicMock(), InMemoryGenerationStops()), action,
    )(selection)

    assert affected == 4
    getattr(job_repo, action).assert_called_once_with(selection)


@pytest.mark.unit
def test_cancelling_a_kind_or_a_source_stops_a_run_still_queueing_it() -> None:
    stops = InMemoryGenerationStops()
    queue = ManageQueueUseCase(MagicMock(), MagicMock(), stops)
    mark = stops.mark()

    queue.cancel(JobSelection(job_id=7))
    assert stops.stopped_since(mark, JobType.MEANING, {SOURCE_ID, 2}) == set()

    queue.cancel(JobSelection(job_type=JobType.MEANING, source_id=SOURCE_ID))
    assert stops.stopped_since(mark, JobType.MEANING, {SOURCE_ID, 2}) == {SOURCE_ID}
    assert stops.stopped_since(mark, JobType.TTS, {SOURCE_ID, 2}) == set()

    queue.cancel(JobSelection(job_type=JobType.TTS))
    assert stops.stopped_since(mark, JobType.TTS, {SOURCE_ID, 2}) == {SOURCE_ID, 2}
    assert stops.stopped_since(stops.mark(), JobType.TTS, {SOURCE_ID, 2}) == set()
