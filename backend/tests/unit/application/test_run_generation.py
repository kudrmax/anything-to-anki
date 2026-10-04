from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.cancel_generation import CancelGenerationUseCase
from backend.application.use_cases.get_generation_status import GetGenerationStatusUseCase
from backend.application.use_cases.run_generation import RunGenerationUseCase
from backend.application.utils.generation_targets import (
    MeaningTarget,
    MediaTarget,
    PolishTarget,
    PronunciationTarget,
    TTSTarget,
)
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.job import Job
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import GenerationBlockedError, GenerationNotSupportedError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.application.dto.generation_dtos import GenerationKindStatusDTO

SOURCE_ID = 9
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _meaning(cid: int) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=cid, meaning="m", translation="t", synonyms=None, examples=None,
        ipa=None, generated_at=NOW,
    )


def _candidate(
    cid: int,
    status: CandidateStatus = CandidateStatus.PENDING,
    *,
    meaning: bool = False,
    media: CandidateMedia | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=SOURCE_ID,
        lemma="stale",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment="The air was stale",
        fragment_purity="clean",
        occurrences=1,
        status=status,
        meaning=_meaning(cid) if meaning else None,
        media=media,
    )


def _job(cid: int, status: JobStatus, job_type: JobType = JobType.MEANING) -> Job:
    return Job(
        id=cid * 100, job_type=job_type, candidate_id=cid, source_id=SOURCE_ID,
        status=status, error=None, created_at=NOW, started_at=None,
    )


def _source(content_type: ContentType = ContentType.TEXT, video_path: str | None = None) -> Source:
    return Source(
        id=SOURCE_ID, raw_text="t", status=SourceStatus.DONE,
        input_method=InputMethod.TEXT_PASTED, content_type=content_type, video_path=video_path,
    )


class _Setup:
    def __init__(
        self,
        candidates: list[StoredCandidate],
        jobs: list[Job] | None = None,
        source: Source | None = None,
        video_downloading: bool = False,
    ) -> None:
        self.source_repo = MagicMock()
        self.source_repo.get_by_id.return_value = source or _source()
        self.candidate_repo = MagicMock()
        self.candidate_repo.get_by_source.return_value = candidates
        self.meaning_repo = MagicMock()
        self.job_repo = MagicMock()
        by_candidate: dict[int, dict[str, Job]] = {}
        for job in jobs or []:
            assert job.candidate_id is not None
            by_candidate.setdefault(job.candidate_id, {})[job.job_type.value] = job
        self.job_repo.get_jobs_for_candidates.return_value = by_candidate
        self.job_repo.has_active_jobs_for_source.return_value = video_downloading
        sorter = MagicMock()
        sorter.sort.side_effect = lambda cs, _source, _order: list(reversed(cs))
        targets = [
            PolishTarget(self.candidate_repo),
            MeaningTarget(self.meaning_repo),
            MediaTarget(),
            PronunciationTarget(),
            TTSTarget(),
        ]
        self.run = RunGenerationUseCase(
            source_repo=self.source_repo, candidate_repo=self.candidate_repo,
            job_repo=self.job_repo, candidate_sorter=sorter, targets=targets,
        )
        self.status = GetGenerationStatusUseCase(
            source_repo=self.source_repo, candidate_repo=self.candidate_repo,
            job_repo=self.job_repo, targets=targets,
        )

    def kind_status(self, kind: GenerationKind) -> GenerationKindStatusDTO:
        return next(k for k in self.status.execute(SOURCE_ID).kinds if k.kind == kind)

    def queued_ids(self) -> list[int | None]:
        return [j.candidate_id for j in self.job_repo.create_bulk.call_args.args[0]]


def _mixed_meanings() -> _Setup:
    return _Setup(
        candidates=[
            _candidate(1, meaning=True),
            _candidate(2),
            _candidate(3),
            _candidate(4),
            _candidate(5, CandidateStatus.KNOWN),
        ],
        jobs=[_job(3, JobStatus.QUEUED), _job(4, JobStatus.FAILED)],
    )


@pytest.mark.unit
class TestRunGeneration:
    def test_missing_queues_only_cards_nothing_was_made_for(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.MISSING)

        assert queued == 1
        assert setup.queued_ids() == [2]
        setup.job_repo.delete_failed_by_source_and_type.assert_not_called()
        setup.meaning_repo.delete_by_candidate_id.assert_not_called()

    def test_failed_requeues_failed_cards_and_drops_their_old_jobs(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.FAILED)

        assert queued == 1
        assert setup.queued_ids() == [4]
        setup.job_repo.delete_failed_by_source_and_type.assert_called_once_with(
            SOURCE_ID, JobType.MEANING,
        )

    def test_all_replaces_every_card_except_ones_already_running(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.ALL)

        assert queued == 3
        assert setup.queued_ids() == [4, 2, 1]  # the sorter's order
        discarded = [c.args[0] for c in setup.meaning_repo.delete_by_candidate_id.call_args_list]
        assert discarded == [1, 2, 4]

    def test_regenerating_phrases_drops_old_polish(self) -> None:
        candidate = _candidate(1)
        candidate.polished_fragment = "The air was bad"
        setup = _Setup([candidate])

        setup.run.execute(SOURCE_ID, GenerationKind.POLISH, GenerationScope.ALL)

        setup.candidate_repo.set_polished_fragment.assert_called_once_with(1, None)
        assert setup.queued_ids() == [1]

    def test_nothing_to_queue_creates_no_jobs(self) -> None:
        setup = _Setup([_candidate(1, meaning=True)])

        assert setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.MISSING) == 0
        setup.job_repo.create_bulk.assert_not_called()

    def test_kind_the_source_has_no_use_for_is_refused(self) -> None:
        setup = _Setup([_candidate(1)], source=_source(ContentType.VIDEO, video_path="v.mp4"))

        with pytest.raises(GenerationNotSupportedError):
            setup.run.execute(SOURCE_ID, GenerationKind.TTS, GenerationScope.MISSING)

    def test_media_without_video_is_blocked(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path=None, audio_path=None,
            start_ms=0, end_ms=1000, generated_at=None,
        )
        setup = _Setup([_candidate(1, media=media)], source=_source(ContentType.VIDEO))

        with pytest.raises(GenerationBlockedError):
            setup.run.execute(SOURCE_ID, GenerationKind.MEDIA, GenerationScope.MISSING)
        setup.job_repo.create_bulk.assert_not_called()


@pytest.mark.unit
class TestGetGenerationStatus:
    def test_counts_every_active_card_once(self) -> None:
        setup = _mixed_meanings()

        status = setup.status.execute(SOURCE_ID)

        meaning = next(k for k in status.kinds if k.kind == GenerationKind.MEANING)
        assert (meaning.total, meaning.done, meaning.running, meaning.failed, meaning.missing) == (
            4, 1, 1, 1, 1,
        )
        assert status.in_progress is True

    def test_done_card_with_a_stale_failure_counts_as_done(self) -> None:
        setup = _Setup([_candidate(1, meaning=True)], jobs=[_job(1, JobStatus.FAILED)])

        meaning = setup.kind_status(GenerationKind.MEANING)

        assert (meaning.done, meaning.failed) == (1, 0)

    def test_text_source_gets_phrases_meanings_pronunciation_and_speech(self) -> None:
        setup = _Setup([_candidate(1)])

        kinds = [k.kind for k in setup.status.execute(SOURCE_ID).kinds]

        assert kinds == [
            GenerationKind.POLISH, GenerationKind.MEANING,
            GenerationKind.PRONUNCIATION, GenerationKind.TTS,
        ]

    def test_video_source_gets_media_instead_of_speech(self) -> None:
        setup = _Setup(
            [_candidate(1)], source=_source(ContentType.VIDEO), video_downloading=True,
        )

        status = setup.status.execute(SOURCE_ID)

        assert [k.kind for k in status.kinds] == [
            GenerationKind.MEANING, GenerationKind.MEDIA, GenerationKind.PRONUNCIATION,
        ]
        media = next(k for k in status.kinds if k.kind == GenerationKind.MEDIA)
        assert media.blocked_by == GenerationBlocker.VIDEO_DOWNLOADING
        assert media.total == 0  # the card has no timecodes
        assert status.in_progress is True

    def test_speech_without_audio_file_is_missing(self) -> None:
        candidate = _candidate(1)
        candidate.tts = CandidateTTS(candidate_id=1, audio_path=None, generated_at=None)
        setup = _Setup([candidate])

        tts = setup.kind_status(GenerationKind.TTS)

        assert (tts.done, tts.missing) == (0, 1)


@pytest.mark.unit
def test_cancel_drops_queued_and_running_jobs_of_the_kind() -> None:
    job_repo = MagicMock()
    job_repo.delete_by_source_and_type.return_value = 3

    cancelled = CancelGenerationUseCase(job_repo).execute(SOURCE_ID, GenerationKind.TTS)

    assert cancelled == 3
    job_repo.delete_by_source_and_type.assert_called_once_with(SOURCE_ID, JobType.TTS)
