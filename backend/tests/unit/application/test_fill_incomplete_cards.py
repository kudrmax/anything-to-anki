from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.fill_incomplete_cards import FillIncompleteCardsUseCase
from backend.application.use_cases.get_export_cards import GetExportCardsUseCase
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.job import Job
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.card_fill_skip import CardFillSkip
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.missing_card_part import MissingCardPart
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus

from tests.export_support import ExportCards, export_card, fill_planner
from tests.phrase_support import phrase
from tests.unit.application.scope_fakes import sources_scope_resolver
from tests.unit.application.source_fakes import InMemorySourceRepository

if TYPE_CHECKING:
    from backend.application.utils.card_fill import CardFill
    from backend.application.utils.export_queue import ExportCard

TEXT = 1
VIDEO = 2
AT = datetime(2026, 4, 7, tzinfo=UTC)


def _sources(video_path: str | None = "/v/2.mp4") -> InMemorySourceRepository:
    return InMemorySourceRepository([
        Source(id=TEXT, status=SourceStatus.DONE, title="Article", kind=Kind.TEXT),
        Source(
            id=VIDEO, status=SourceStatus.DONE, title="Episode", format=Format.YOUTUBE,
            source_url="https://youtu.be/x", video_path=video_path,
        ),
    ])


def _meaning(word_id: int) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=word_id, meaning="a meaning", translation=None, synonyms=None,
        examples=None, ipa=None, generated_at=AT,
    )


def _timed(word_id: int, audio_path: str | None = None) -> CandidateMedia:
    return CandidateMedia(
        candidate_id=word_id, screenshot_path=None, audio_path=audio_path,
        start_ms=1000, end_ms=2000, generated_at=AT,
    )


def _tts(word_id: int) -> CandidateTTS:
    return CandidateTTS(candidate_id=word_id, audio_path="tts.mp3", generated_at=AT)


def _card(
    word_id: int,
    source_id: int,
    *,
    meaning: bool = False,
    media: CandidateMedia | None = None,
    tts: bool = False,
    kind: DecisionKind | None = None,
) -> ExportCard:
    word = StoredCandidate(
        id=word_id, source_id=source_id, lemma=f"word{word_id}", pos="NOUN",
        cefr_level="B2", zipf_frequency=3.5, occurrences=1, status=WordStatus.LEARN,
    )
    return export_card(
        word, phrase(f"a phrase with word{word_id}", f"word{word_id}"),
        meaning=_meaning(word_id) if meaning else None,
        media=media,
        tts=_tts(word_id) if tts else None,
        kind=kind,
    )


def _jobs(
    active: dict[int, JobType] | None = None, failed: dict[int, JobType] | None = None,
) -> MagicMock:
    """Jobs held by phrases: an active and a failed one of a type per phrase id."""
    def of_phrases(phrase_ids: list[int]) -> dict[int, dict[str, Job]]:
        held: dict[int, dict[str, Job]] = {}
        held_jobs = ((JobStatus.RUNNING, active or {}), (JobStatus.FAILED, failed or {}))
        for status, by_phrase in held_jobs:
            for phrase_id, job_type in by_phrase.items():
                if phrase_id in phrase_ids:
                    held.setdefault(phrase_id, {})[job_type.value] = Job(
                        id=1, job_type=job_type, candidate_id=None, source_id=TEXT,
                        status=status, error=None, created_at=AT, started_at=None,
                        phrase_id=phrase_id,
                    )
        return held

    repo = MagicMock()
    repo.get_jobs_for_phrases.side_effect = of_phrases
    repo.get_jobs_for_candidates.return_value = {}
    repo.has_active_jobs_for_source.return_value = False
    return repo


def _plan_of(
    card: ExportCard, sources: InMemorySourceRepository, **planner: MagicMock,
) -> tuple[CardFill, list[Job]]:
    plan = fill_planner(sources, **planner).plan([card])
    return plan.of(card.phrase_id), plan.jobs


@pytest.mark.unit
class TestCardFillPlanner:
    def test_text_card_gets_meaning_and_tts(self) -> None:
        fill, jobs = _plan_of(_card(1, TEXT), _sources())

        assert fill.queued == (MissingCardPart.MEANING, MissingCardPart.AUDIO)
        assert [j.job_type for j in jobs] == [JobType.MEANING, JobType.TTS]

    def test_video_card_gets_a_clip_cut_from_the_video(self) -> None:
        card = _card(1, VIDEO, meaning=True, media=_timed(1))

        fill, jobs = _plan_of(card, _sources())

        assert fill.queued == (MissingCardPart.AUDIO,)
        assert [(j.job_type, j.phrase_id) for j in jobs] == [(JobType.MEDIA, card.phrase_id)]

    def test_deleted_video_skips_the_clip_and_still_fills_the_meaning(self) -> None:
        fill, jobs = _plan_of(_card(1, VIDEO, media=_timed(1)), _sources(video_path=None))

        assert fill.queued == (MissingCardPart.MEANING,)
        assert [(s.part, s.reason) for s in fill.skipped] == [
            (MissingCardPart.AUDIO, CardFillSkip.VIDEO_NOT_DOWNLOADED),
        ]
        assert [j.job_type for j in jobs] == [JobType.MEANING]

    def test_video_on_its_way_skips_the_clip(self) -> None:
        jobs = _jobs()
        jobs.has_active_jobs_for_source.return_value = True

        fill, _ = _plan_of(
            _card(1, VIDEO, meaning=True, media=_timed(1)), _sources(video_path=None),
            job_repo=jobs,
        )

        assert [s.reason for s in fill.skipped] == [CardFillSkip.VIDEO_DOWNLOADING]

    def test_phrase_without_time_skips_the_clip(self) -> None:
        fill, jobs = _plan_of(_card(1, VIDEO, meaning=True), _sources())

        assert [s.reason for s in fill.skipped] == [CardFillSkip.NO_PHRASE_TIME]
        assert jobs == []

    def test_part_a_job_is_making_is_left_to_it(self) -> None:
        card = _card(1, TEXT)

        running = _jobs(active={card.phrase_id: JobType.MEANING})

        fill, jobs = _plan_of(card, _sources(), job_repo=running)

        assert fill.generating == (MissingCardPart.MEANING,)
        assert [j.job_type for j in jobs] == [JobType.TTS]

    def test_failed_part_is_tried_again(self) -> None:
        card = _card(1, TEXT, tts=True)

        failed = _jobs(failed={card.phrase_id: JobType.MEANING})

        fill, jobs = _plan_of(card, _sources(), job_repo=failed)

        assert fill.queued == (MissingCardPart.MEANING,)
        assert [j.job_type for j in jobs] == [JobType.MEANING]

    def test_busy_source_skips_every_part(self) -> None:
        lock = MagicMock()
        lock.held.return_value = SourceOperationKind.PROCESS

        fill, jobs = _plan_of(_card(1, TEXT), _sources(), lock=lock)

        assert {s.reason for s in fill.skipped} == {CardFillSkip.SOURCE_BUSY}
        assert jobs == []

    def test_cloze_words_are_left_to_the_user(self) -> None:
        card = _card(1, TEXT, meaning=True, tts=True, kind=DecisionKind.CLOZE)

        fill, jobs = _plan_of(card, _sources())

        assert [(s.part, s.reason) for s in fill.skipped] == [
            (MissingCardPart.CLOZE, CardFillSkip.CLOZE_NEEDS_CHOICE),
        ]
        assert jobs == []


def _export(
    cards: ExportCards, sources: InMemorySourceRepository, jobs: MagicMock,
) -> GetExportCardsUseCase:
    return GetExportCardsUseCase(
        export_queue=cards.queue(),
        source_repo=sources,
        cloze_builder=ClozeBuilder(),
        scope_resolver=sources_scope_resolver(TEXT, VIDEO),
        fill_planner=fill_planner(sources, job_repo=jobs),
    )


@pytest.mark.unit
class TestExportShowsTheFill:
    def test_counts_cards_to_fill_being_made_and_skipped(self) -> None:
        cards = ExportCards()
        generating = _card(3, TEXT, tts=True)
        cards.put([
            _card(1, TEXT),
            _card(2, VIDEO, media=_timed(2)),
            generating,
            _card(4, VIDEO, meaning=True, media=_timed(4, audio_path="clip.mp3")),
        ])

        running = _jobs(active={generating.phrase_id: JobType.MEANING})

        result = _export(cards, _sources(video_path=None), running).execute(SourceScope.all())

        assert result.fill.fillable == 2
        assert result.fill.generating == 1
        assert [(s.reason, s.cards) for s in result.fill.skipped] == [
            (CardFillSkip.VIDEO_NOT_DOWNLOADED, 1),
        ]
        video_card = result.incomplete[1].cards[0]
        assert [(s.part, s.reason) for s in video_card.cannot_fill] == [
            (MissingCardPart.AUDIO, CardFillSkip.VIDEO_NOT_DOWNLOADED),
        ]
        assert result.incomplete[0].cards[1].generating == [MissingCardPart.MEANING]


@pytest.mark.unit
class TestFillIncompleteCards:
    def test_queues_what_incomplete_cards_lack_and_leaves_ready_ones(self) -> None:
        cards = ExportCards()
        incomplete = _card(1, TEXT, tts=True)
        cards.put([incomplete, _card(2, TEXT, meaning=True, tts=True)])
        sources = _sources()
        jobs = _jobs()
        jobs.enqueue.side_effect = lambda queued: queued

        queued = FillIncompleteCardsUseCase(
            export_queue=cards.queue(),
            scope_resolver=sources_scope_resolver(TEXT, VIDEO),
            planner=fill_planner(sources, job_repo=jobs),
            job_repo=jobs,
            unit_of_work=MagicMock(),
        ).execute(SourceScope.all())

        assert queued == 1
        [enqueued] = jobs.enqueue.call_args.args
        assert [(j.job_type, j.phrase_id) for j in enqueued] == [
            (JobType.MEANING, incomplete.phrase_id),
        ]
