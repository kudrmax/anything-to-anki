from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.cancel_generation import CancelGenerationUseCase
from backend.application.use_cases.get_generation_status import GetGenerationStatusUseCase
from backend.application.use_cases.run_generation import RunGenerationUseCase
from backend.application.utils.generation_targets import (
    GenerationCards,
    MeaningTarget,
    MediaTarget,
    PolishTarget,
    PronunciationTarget,
    TTSTarget,
)
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    GenerationBlockedError,
    GenerationNotSupportedError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.job_selection import JobSelection
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.application.dto.generation_dtos import GenerationKindStatusDTO

SOURCE_ID = 9
NOW = datetime(2026, 1, 1, tzinfo=UTC)
PHRASES_PER_WORD = 10


def _meaning(cid: int) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=cid, meaning="m", translation="t", synonyms=None, examples=None,
        ipa=None, generated_at=NOW,
    )


def _word(cid: int, status: CandidateStatus = CandidateStatus.PENDING) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=SOURCE_ID,
        lemma=f"stale{cid}",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
        source_phrase=phrase("The air was stale", "stale"),
        occurrences=1,
        status=status,
    )


def _phrase(
    cid: int,
    n: int = 0,
    *,
    meaning: bool = False,
    media: CandidateMedia | None = None,
    revision: int = 0,
    skipped: bool = False,
) -> Occurrence:
    """The n-th shown phrase of word `cid`; its id is cid * 10 + n."""
    return Occurrence(
        id=cid * PHRASES_PER_WORD + n,
        candidate_id=cid,
        origin=OccurrenceOrigin.AUTO,
        source_phrase=phrase("The air was stale", "stale"),
        phrase_position=None,
        key=None,
        fragment_score=None,
        revision=revision,
        shown_by=ShownBy.SELECTION,
        skipped=skipped,
        meaning=_meaning(cid) if meaning else None,
        media=media,
    )


def _job(phrase_id: int, status: JobStatus, job_type: JobType = JobType.MEANING) -> Job:
    return Job(
        id=phrase_id * 100, job_type=job_type, candidate_id=phrase_id // PHRASES_PER_WORD,
        source_id=SOURCE_ID, status=status, error=None, created_at=NOW, started_at=None,
        phrase_id=phrase_id, phrase_revision=0,
    )


def _source(source_format: Format = Format.PLAIN, video_path: str | None = None) -> Source:
    return Source(
        id=SOURCE_ID, status=SourceStatus.DONE,
        video_path=video_path, format=source_format, kind=Kind.TEXT,
    )


class _Setup:
    def __init__(
        self,
        cards: list[tuple[StoredCandidate, list[Occurrence]]],
        jobs: list[Job] | None = None,
        source: Source | None = None,
        video_downloading: bool = False,
        busy_with: SourceOperationKind | None = None,
    ) -> None:
        self.source_repo = MagicMock()
        self.source_repo.get_by_id.return_value = source or _source()
        self.candidate_repo = MagicMock()
        self.candidate_repo.get_by_source.return_value = [word for word, _ in cards]
        self.occurrence_repo = MagicMock()
        self.occurrence_repo.shown_by_word.return_value = {
            word.id: shown for word, shown in cards if shown
        }
        self.meaning_repo = MagicMock()
        self.job_repo = MagicMock()
        self.job_repo.enqueue.side_effect = lambda jobs: jobs
        by_phrase: dict[int, dict[str, Job]] = {}
        by_word: dict[int, dict[str, Job]] = {}
        for job in jobs or []:
            if job.phrase_id is not None:
                by_phrase.setdefault(job.phrase_id, {})[job.job_type.value] = job
            else:
                assert job.candidate_id is not None
                by_word.setdefault(job.candidate_id, {})[job.job_type.value] = job
        self.job_repo.get_jobs_for_phrases.return_value = by_phrase
        self.job_repo.get_jobs_for_candidates.return_value = by_word
        self.job_repo.has_active_jobs_for_source.return_value = video_downloading
        self.lock = MagicMock()
        self.lock.held.return_value = busy_with
        sorter = MagicMock()
        sorter.sort.side_effect = lambda cs, _order: list(reversed(cs))
        targets = [
            PolishTarget(self.occurrence_repo),
            MeaningTarget(self.meaning_repo),
            MediaTarget(),
            PronunciationTarget(),
            TTSTarget(),
        ]
        generation_cards = GenerationCards(self.candidate_repo, self.occurrence_repo)
        self.run = RunGenerationUseCase(
            source_repo=self.source_repo, cards=generation_cards,
            job_repo=self.job_repo, candidate_sorter=sorter, targets=targets, lock=self.lock,
        )
        self.status = GetGenerationStatusUseCase(
            source_repo=self.source_repo, cards=generation_cards,
            job_repo=self.job_repo, targets=targets,
        )

    def kind_status(self, kind: GenerationKind) -> GenerationKindStatusDTO:
        return next(k for k in self.status.execute(SOURCE_ID).kinds if k.kind == kind)

    def queued(self) -> list[tuple[int | None, int | None, int | None]]:
        return [
            (j.candidate_id, j.phrase_id, j.phrase_revision)
            for j in self.job_repo.enqueue.call_args.args[0]
        ]

    def queued_phrases(self) -> list[int | None]:
        return [phrase_id for _, phrase_id, _ in self.queued()]


def _one(
    cid: int,
    status: CandidateStatus = CandidateStatus.PENDING,
    *,
    meaning: bool = False,
    media: CandidateMedia | None = None,
) -> tuple[StoredCandidate, list[Occurrence]]:
    """A word with one shown phrase."""
    return _word(cid, status), [_phrase(cid, meaning=meaning, media=media)]


def _mixed_meanings() -> _Setup:
    return _Setup(
        cards=[
            _one(1, meaning=True),
            _one(2),
            _one(3),
            _one(4),
            _one(5, CandidateStatus.KNOWN),
        ],
        jobs=[_job(30, JobStatus.QUEUED), _job(40, JobStatus.FAILED)],
    )


@pytest.mark.unit
class TestRunGeneration:
    def test_missing_queues_only_cards_nothing_was_made_for(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.MISSING)

        assert queued == 1
        assert setup.queued_phrases() == [20]
        setup.meaning_repo.delete_by_phrase_id.assert_not_called()

    def test_failed_requeues_only_failed_cards(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.FAILED)

        assert queued == 1
        assert setup.queued_phrases() == [40]

    def test_all_replaces_every_card_except_ones_already_running(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.ALL)

        assert queued == 3
        assert setup.queued_phrases() == [40, 20, 10]  # the sorter's order
        discarded = [c.args[0] for c in setup.meaning_repo.delete_by_phrase_id.call_args_list]
        assert discarded == [10, 20, 40]

    def test_regenerating_phrases_drops_old_polish(self) -> None:
        shown = replace(_phrase(1), polished_phrase=phrase("The air was bad", "bad"))
        setup = _Setup([(_word(1), [shown])])

        setup.run.execute(SOURCE_ID, GenerationKind.POLISH, GenerationScope.ALL)

        setup.occurrence_repo.write_text.assert_called_once_with(
            10, shown.source_phrase, None, polished=None,
        )
        assert setup.queued_phrases() == [10]

    def test_nothing_to_queue_creates_no_jobs(self) -> None:
        setup = _Setup([_one(1, meaning=True)])

        assert setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.MISSING) == 0
        assert setup.queued() == []

    def test_kind_the_source_has_no_use_for_is_refused(self) -> None:
        setup = _Setup([_one(1)], source=_source(Format.VIDEO_FILE, video_path="v.mp4"))

        with pytest.raises(GenerationNotSupportedError):
            setup.run.execute(SOURCE_ID, GenerationKind.TTS, GenerationScope.MISSING)

    def test_media_without_video_is_blocked(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path=None, audio_path=None,
            start_ms=0, end_ms=1000, generated_at=None,
        )
        setup = _Setup([_one(1, media=media)], source=_source(Format.VIDEO_FILE))

        with pytest.raises(GenerationBlockedError):
            setup.run.execute(SOURCE_ID, GenerationKind.MEDIA, GenerationScope.MISSING)
        setup.job_repo.enqueue.assert_not_called()


@pytest.mark.unit
class TestGenerationByPhrase:
    def test_every_shown_phrase_of_a_word_gets_its_own_job(self) -> None:
        setup = _Setup([(_word(1), [_phrase(1, 0), _phrase(1, 1, revision=3)])])

        queued = setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.MISSING)

        assert queued == 2
        assert sorted(setup.queued()) == [(1, 10, 0), (1, 11, 3)]

    def test_cards_of_a_word_follow_the_order_of_words(self) -> None:
        setup = _Setup([
            (_word(1), [_phrase(1, 0), _phrase(1, 1)]),
            (_word(2), [_phrase(2, 0)]),
        ])

        setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.MISSING)

        assert setup.queued_phrases() == [20, 10, 11]

    def test_a_skipped_phrase_gets_nothing(self) -> None:
        setup = _Setup([(_word(1), [_phrase(1, 0, skipped=True), _phrase(1, 1)])])

        setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.MISSING)

        assert setup.queued_phrases() == [11]

    def test_a_phrase_with_its_meaning_is_done_while_its_neighbour_is_not(self) -> None:
        setup = _Setup([(_word(1), [_phrase(1, 0, meaning=True), _phrase(1, 1)])])

        meaning = setup.kind_status(GenerationKind.MEANING)

        assert (meaning.total, meaning.done, meaning.missing) == (2, 1, 1)

    def test_pronunciation_belongs_to_the_word(self) -> None:
        setup = _Setup([(_word(1), [_phrase(1, 0), _phrase(1, 1)]), _one(2)])
        done = _word(2)
        done.pronunciation = CandidatePronunciation(
            candidate_id=2, us_audio_path="us.mp3", uk_audio_path=None, generated_at=NOW,
        )
        setup.candidate_repo.get_by_source.return_value = [_word(1), done]

        queued = setup.run.execute(
            SOURCE_ID, GenerationKind.PRONUNCIATION, GenerationScope.MISSING,
        )

        assert queued == 1
        assert setup.queued() == [(1, None, None)]
        pronunciation = setup.kind_status(GenerationKind.PRONUNCIATION)
        assert (pronunciation.total, pronunciation.done) == (2, 1)

    def test_a_word_with_no_shown_phrase_gets_nothing(self) -> None:
        setup = _Setup([(_word(1), [])])

        assert setup.run.execute(
            SOURCE_ID, GenerationKind.PRONUNCIATION, GenerationScope.MISSING,
        ) == 0


@pytest.mark.unit
class TestBusySource:
    def test_generation_is_refused_while_the_source_is_rebuilt(self) -> None:
        setup = _Setup([_one(1)], busy_with=SourceOperationKind.REBUILD)

        with pytest.raises(SourceOperationBusyError):
            setup.run.execute(SOURCE_ID, GenerationKind.MEANING, GenerationScope.MISSING)
        setup.job_repo.enqueue.assert_not_called()
        setup.meaning_repo.delete_by_phrase_id.assert_not_called()


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
        setup = _Setup([_one(1, meaning=True)], jobs=[_job(10, JobStatus.FAILED)])

        meaning = setup.kind_status(GenerationKind.MEANING)

        assert (meaning.done, meaning.failed) == (1, 0)

    def test_text_source_gets_phrases_meanings_pronunciation_and_speech(self) -> None:
        setup = _Setup([_one(1)])

        kinds = [k.kind for k in setup.status.execute(SOURCE_ID).kinds]

        assert kinds == [
            GenerationKind.POLISH, GenerationKind.MEANING,
            GenerationKind.PRONUNCIATION, GenerationKind.TTS,
        ]

    def test_video_source_gets_media_instead_of_speech(self) -> None:
        setup = _Setup(
            [_one(1)], source=_source(Format.VIDEO_FILE), video_downloading=True,
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
        shown = replace(
            _phrase(1), tts=CandidateTTS(candidate_id=1, audio_path=None, generated_at=None),
        )
        setup = _Setup([(_word(1), [shown])])

        tts = setup.kind_status(GenerationKind.TTS)

        assert (tts.done, tts.missing) == (0, 1)


@pytest.mark.unit
def test_cancel_drops_queued_and_running_jobs_of_the_kind() -> None:
    job_repo = MagicMock()
    job_repo.cancel.return_value = 3

    cancelled = CancelGenerationUseCase(job_repo).execute(SOURCE_ID, GenerationKind.TTS)

    assert cancelled == 3
    job_repo.cancel.assert_called_once_with(
        JobSelection(job_type=JobType.TTS, source_id=SOURCE_ID),
    )
