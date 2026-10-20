from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.cancel_generation import CancelGenerationUseCase
from backend.application.use_cases.get_generation_status import GetGenerationStatusUseCase
from backend.application.use_cases.run_generation import RunGenerationUseCase
from backend.application.utils.candidate_sorter import ArrangedCards
from backend.application.utils.generation_targets import (
    GenerationCards,
    MeaningTarget,
    MediaTarget,
    PolishTarget,
    PronunciationTarget,
    TTSTarget,
)
from backend.application.utils.source_scope_resolver import SourceScopeResolver
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.collection import Collection
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import (
    GenerationBlockedError,
    GenerationNotSupportedError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.generation_blocker import GenerationBlocker
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.job_selection import JobSelection
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_scope import SourceScope
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus

from tests.card_support import PhraseWordStates
from tests.decision_support import NOW as REQUEST_MOMENT
from tests.phrase_support import phrase
from tests.unit.application.collection_fakes import InMemoryCollectionRepository
from tests.unit.application.source_fakes import InMemorySourceRepository
from tests.vocabulary_support import user_vocabulary

if TYPE_CHECKING:
    from backend.application.dto.generation_dtos import GenerationKindStatusDTO
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.value_objects.review_card import ReviewCard

SOURCE_ID = 9
SCOPE = SourceScope.source(SOURCE_ID)
NOW = datetime(2026, 1, 1, tzinfo=UTC)
PHRASES_PER_WORD = 10
EXPORTED = REQUEST_MOMENT - timedelta(days=1)   # in Anki, not Known yet


def _meaning(cid: int) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=cid, meaning="m", translation="t", synonyms=None, examples=None,
        ipa=None, generated_at=NOW,
    )


def _word(cid: int, status: WordStatus = WordStatus.NEW) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=SOURCE_ID,
        lemma=f"stale{cid}",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
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
    decision: DecisionKind | None = None,
) -> Occurrence:
    """The n-th shown phrase of word `cid`; its id is cid * 10 + n."""
    return Occurrence(
        id=cid * PHRASES_PER_WORD + n,
        candidate_id=cid,
        origin=OccurrenceOrigin.AUTO,
        source_phrase=phrase("The air was stale", "stale"),
        phrase_position=None,
        key=None,
        fragment_score=None, earned_section=CandidateSection.READY,
        revision=revision,
        shown_by=ShownBy.SELECTION,
        choice=(
            CardChoice.CLOZE if decision is DecisionKind.CLOZE
            else CardChoice.LEARN if decision is not None
            else CardChoice.SKIP if skipped else CardChoice.NONE
        ),
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


def _vocabulary_holding(elsewhere: dict[str, ElsewhereStatus]) -> UserVocabulary:
    """The user's words with each lemma held in another source as `elsewhere` says."""
    def held(status: ElsewhereStatus) -> set[str]:
        return {lemma for lemma, held in elsewhere.items() if held is status}

    known = MagicMock()
    known.get_all_pairs.return_value = {(lemma, None) for lemma in held(ElsewhereStatus.KNOWN)}
    return user_vocabulary(
        known,
        learning_lemmas=held(ElsewhereStatus.LEARN),
        active_since={lemma: (EXPORTED,) for lemma in held(ElsewhereStatus.LEARNING)},
    )


class _Setup:
    def __init__(
        self,
        cards: list[tuple[StoredCandidate, list[Occurrence]]],
        jobs: list[Job] | None = None,
        source: Source | None = None,
        video_downloading: bool = False,
        busy_with: SourceOperationKind | None = None,
        elsewhere: dict[str, ElsewhereStatus] | None = None,
        extra_phrases: frozenset[int] = frozenset(),
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
        sorter.arrange.side_effect = lambda cs, _order, *, source_order: ArrangedCards(
            cards=_words_reversed(cs), sections={},
        )
        sorter.open_sections.side_effect = lambda cs: {
            c.phrase_id: (
                CandidateSection.EXTRA if c.phrase_id in extra_phrases
                else CandidateSection.READY
            )
            for c in cs
        }
        stamper = MagicMock()
        stamper.earned.return_value = CandidateSection.EXTRA
        targets = [
            PolishTarget(self.occurrence_repo, stamper),
            MeaningTarget(self.meaning_repo),
            MediaTarget(),
            PronunciationTarget(),
            TTSTarget(),
        ]
        generation_cards = GenerationCards(
            self.candidate_repo, self.occurrence_repo,
            PhraseWordStates(
                lambda: [word for word, _ in cards],
                lambda word_id: next((shown for w, shown in cards if w.id == word_id), []),
            ),
            _vocabulary_holding(elsewhere or {}),
        )
        resolver = SourceScopeResolver(self.source_repo, MagicMock())
        self.run = RunGenerationUseCase(
            scope_resolver=resolver, cards=generation_cards,
            job_repo=self.job_repo, candidate_sorter=sorter, targets=targets, lock=self.lock,
        )
        self.status = GetGenerationStatusUseCase(
            scope_resolver=resolver, cards=generation_cards,
            job_repo=self.job_repo, candidate_sorter=sorter, targets=targets,
        )

    def kind_status(self, kind: GenerationKind) -> GenerationKindStatusDTO:
        return next(k for k in self.status.execute(SCOPE).kinds if k.kind == kind)

    def queued(self) -> list[tuple[int | None, int | None, int | None]]:
        return [
            (j.candidate_id, j.phrase_id, j.phrase_revision)
            for j in self.job_repo.enqueue.call_args.args[0]
        ]

    def queued_phrases(self) -> list[int | None]:
        return [phrase_id for _, phrase_id, _ in self.queued()]


def _words_reversed(cards: list[ReviewCard]) -> list[ReviewCard]:
    """The sorter of these tests: words in reverse order, the cards of each as made."""
    by_word: dict[int, list[ReviewCard]] = {}
    for card in cards:
        by_word.setdefault(card.word_id, []).append(card)
    return [card for word_id in reversed(by_word) for card in by_word[word_id]]


def _one(
    cid: int,
    status: WordStatus = WordStatus.NEW,
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
            _one(5, WordStatus.KNOWN),
        ],
        jobs=[_job(30, JobStatus.QUEUED), _job(40, JobStatus.FAILED)],
    )


@pytest.mark.unit
class TestRunGeneration:
    def test_missing_queues_only_cards_nothing_was_made_for(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING)

        assert queued == 1
        assert setup.queued_phrases() == [20]
        setup.meaning_repo.delete_by_phrase_id.assert_not_called()

    def test_ready_missing_skips_missing_cards_outside_ready(self) -> None:
        setup = _Setup(
            cards=[_one(1), _one(2), _one(3, meaning=True)],
            extra_phrases=frozenset({20}),
        )

        queued = setup.run.execute(
            SCOPE, GenerationKind.MEANING, GenerationScope.READY_MISSING,
        )

        assert queued == 1
        assert setup.queued_phrases() == [10]

    def test_ready_missing_leaves_cards_out_of_play(self) -> None:
        setup = _Setup(cards=[_one(1), _one(2, WordStatus.KNOWN)])

        setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.READY_MISSING)

        assert setup.queued_phrases() == [10]

    def test_ready_missing_makes_a_word_kind_for_a_word_with_a_ready_phrase(self) -> None:
        setup = _Setup(
            cards=[(_word(1), [_phrase(1, 0), _phrase(1, 1)]), _one(2)],
            extra_phrases=frozenset({10, 20}),
        )

        setup.run.execute(
            SCOPE, GenerationKind.PRONUNCIATION, GenerationScope.READY_MISSING,
        )

        assert [word_id for word_id, _, _ in setup.queued()] == [1]

    def test_failed_requeues_only_failed_cards(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.FAILED)

        assert queued == 1
        assert setup.queued_phrases() == [40]

    def test_all_replaces_every_card_except_ones_already_running(self) -> None:
        setup = _mixed_meanings()

        queued = setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.ALL)

        assert queued == 3
        assert setup.queued_phrases() == [40, 20, 10]  # the sorter's order
        discarded = [c.args[0] for c in setup.meaning_repo.delete_by_phrase_id.call_args_list]
        assert discarded == [10, 20, 40]

    def test_regenerating_phrases_drops_old_polish(self) -> None:
        shown = replace(_phrase(1), polished_phrase=phrase("The air was bad", "bad"))
        setup = _Setup([(_word(1), [shown])])

        setup.run.execute(SCOPE, GenerationKind.POLISH, GenerationScope.ALL)

        setup.occurrence_repo.write_text.assert_called_once_with(
            10, shown.source_phrase, None, earned_section=CandidateSection.EXTRA, polished=None,
        )
        assert setup.queued_phrases() == [10]

    def test_regenerated_polish_is_queued_at_the_revision_its_discard_left(self) -> None:
        shown = replace(_phrase(1), polished_phrase=phrase("The air was bad", "bad"))
        setup = _Setup([(_word(1), [shown])])
        setup.occurrence_repo.shown_by_word.side_effect = [
            {1: [shown]}, {1: [replace(shown, polished_phrase=None, revision=1)]},
        ]

        setup.run.execute(SCOPE, GenerationKind.POLISH, GenerationScope.ALL)

        assert setup.queued() == [(1, 10, 1)]

    def test_nothing_to_queue_creates_no_jobs(self) -> None:
        setup = _Setup([_one(1, meaning=True)])

        assert setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING) == 0
        assert setup.queued() == []

    def test_kind_the_source_has_no_use_for_is_refused(self) -> None:
        setup = _Setup([_one(1)], source=_source(Format.VIDEO_FILE, video_path="v.mp4"))

        with pytest.raises(GenerationNotSupportedError):
            setup.run.execute(SCOPE, GenerationKind.TTS, GenerationScope.MISSING)

    def test_media_without_video_is_blocked(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path=None, audio_path=None,
            start_ms=0, end_ms=1000, generated_at=None,
        )
        setup = _Setup([_one(1, media=media)], source=_source(Format.VIDEO_FILE))

        with pytest.raises(GenerationBlockedError):
            setup.run.execute(SCOPE, GenerationKind.MEDIA, GenerationScope.MISSING)
        setup.job_repo.enqueue.assert_not_called()


@pytest.mark.unit
class TestGenerationByPhrase:
    def test_every_shown_phrase_of_a_word_gets_its_own_job(self) -> None:
        setup = _Setup([(_word(1), [_phrase(1, 0), _phrase(1, 1, revision=3)])])

        queued = setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING)

        assert queued == 2
        assert sorted(setup.queued()) == [(1, 10, 0), (1, 11, 3)]

    def test_cards_of_a_word_follow_the_order_of_words(self) -> None:
        setup = _Setup([
            (_word(1), [_phrase(1, 0), _phrase(1, 1)]),
            (_word(2), [_phrase(2, 0)]),
        ])

        setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING)

        assert setup.queued_phrases() == [20, 10, 11]

    def test_a_skipped_phrase_gets_nothing(self) -> None:
        setup = _Setup([(_word(1), [_phrase(1, 0, skipped=True), _phrase(1, 1)])])

        setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING)

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
            SCOPE, GenerationKind.PRONUNCIATION, GenerationScope.MISSING,
        )

        assert queued == 1
        assert setup.queued() == [(1, None, None)]
        pronunciation = setup.kind_status(GenerationKind.PRONUNCIATION)
        assert (pronunciation.total, pronunciation.done) == (2, 1)

    def test_a_word_with_no_shown_phrase_gets_nothing(self) -> None:
        setup = _Setup([(_word(1), [])])

        assert setup.run.execute(
            SCOPE, GenerationKind.PRONUNCIATION, GenerationScope.MISSING,
        ) == 0


@pytest.mark.unit
class TestCardsNobodyDecidesOn:
    def _learned_with_a_sibling(self) -> _Setup:
        return _Setup([(
            _word(1, WordStatus.LEARN),
            [_phrase(1, 0, decision=DecisionKind.LEARN), _phrase(1, 1)],
        )])

    def test_only_the_decision_card_of_a_learned_word_gets_generation(self) -> None:
        setup = self._learned_with_a_sibling()

        setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING)

        assert setup.queued_phrases() == [10]

    def test_the_status_counts_only_the_decision_card(self) -> None:
        meaning = self._learned_with_a_sibling().kind_status(GenerationKind.MEANING)

        assert (meaning.total, meaning.missing) == (1, 1)

    def test_a_cloze_decision_card_gets_generation(self) -> None:
        setup = _Setup([
            (_word(1, WordStatus.LEARN), [_phrase(1, decision=DecisionKind.CLOZE)]),
        ])

        setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING)

        assert setup.queued_phrases() == [10]

    @pytest.mark.parametrize("elsewhere", list(ElsewhereStatus))
    def test_a_card_decided_elsewhere_gets_nothing(self, elsewhere: ElsewhereStatus) -> None:
        setup = _Setup([_one(1), _one(2)], elsewhere={"stale1": elsewhere})

        setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING)

        assert setup.queued_phrases() == [20]
        meaning = setup.kind_status(GenerationKind.MEANING)
        assert meaning.total == 1


@pytest.mark.unit
class TestBusySource:
    def test_generation_is_refused_while_the_source_is_rebuilt(self) -> None:
        setup = _Setup([_one(1)], busy_with=SourceOperationKind.REBUILD)

        with pytest.raises(SourceOperationBusyError):
            setup.run.execute(SCOPE, GenerationKind.MEANING, GenerationScope.MISSING)
        setup.job_repo.enqueue.assert_not_called()
        setup.meaning_repo.delete_by_phrase_id.assert_not_called()


@pytest.mark.unit
class TestGetGenerationStatus:
    def test_counts_every_active_card_once(self) -> None:
        setup = _mixed_meanings()

        status = setup.status.execute(SCOPE)

        meaning = next(k for k in status.kinds if k.kind == GenerationKind.MEANING)
        assert (meaning.total, meaning.done, meaning.running, meaning.failed, meaning.missing) == (
            4, 1, 1, 1, 1,
        )
        assert status.in_progress is True

    def test_ready_missing_counts_only_missing_cards_in_ready(self) -> None:
        setup = _Setup(
            cards=[_one(1), _one(2), _one(3, meaning=True)],
            extra_phrases=frozenset({20}),
        )

        meaning = setup.kind_status(GenerationKind.MEANING)

        assert (meaning.missing, meaning.ready_missing) == (2, 1)

    def test_done_card_with_a_stale_failure_counts_as_done(self) -> None:
        setup = _Setup([_one(1, meaning=True)], jobs=[_job(10, JobStatus.FAILED)])

        meaning = setup.kind_status(GenerationKind.MEANING)

        assert (meaning.done, meaning.failed) == (1, 0)

    def test_text_source_gets_phrases_meanings_pronunciation_and_speech(self) -> None:
        setup = _Setup([_one(1)])

        kinds = [k.kind for k in setup.status.execute(SCOPE).kinds]

        assert kinds == [
            GenerationKind.POLISH, GenerationKind.MEANING,
            GenerationKind.PRONUNCIATION, GenerationKind.TTS,
        ]

    def test_video_source_gets_media_instead_of_speech(self) -> None:
        setup = _Setup(
            [_one(1)], source=_source(Format.VIDEO_FILE), video_downloading=True,
        )

        status = setup.status.execute(SCOPE)

        assert [k.kind for k in status.kinds] == [
            GenerationKind.MEANING, GenerationKind.MEDIA, GenerationKind.PRONUNCIATION,
        ]
        media = next(k for k in status.kinds if k.kind == GenerationKind.MEDIA)
        assert media.blocked_by == GenerationBlocker.VIDEO_DOWNLOADING
        assert media.total == 0  # the card has no timecodes
        assert status.in_progress is True

    def test_counts_the_videos_a_set_can_still_download(self) -> None:
        """Downloaded, downloading and not downloaded videos in one collection: only the
        last can be downloaded, though the set's media is no longer held back."""
        sources = [
            Source(
                id=source_id, status=SourceStatus.DONE, collection_id=1,
                format=Format.YOUTUBE, source_url="https://youtu.be/x", video_path=video_path,
            )
            for source_id, video_path in [(1, "/v/1.mp4"), (2, None), (3, None), (4, None)]
        ]
        cards = MagicMock()
        cards.of_source.return_value = []
        job_repo = MagicMock()
        job_repo.has_active_jobs_for_source.side_effect = lambda source_id, _types: source_id == 4
        use_case = GetGenerationStatusUseCase(
            scope_resolver=SourceScopeResolver(
                InMemorySourceRepository(sources),
                InMemoryCollectionRepository([Collection(id=1, name="Friends")]),
            ),
            cards=cards, job_repo=job_repo, candidate_sorter=MagicMock(), targets=[MediaTarget()],
        )

        status = use_case.execute(SourceScope.collection(1))

        (media,) = status.kinds
        assert (media.videos_to_download, media.blocked_by) == (2, None)

    def test_a_downloaded_or_downloading_video_is_not_to_download(self) -> None:
        downloaded = _Setup([_one(1)], source=_source(Format.VIDEO_FILE, video_path="/v.mp4"))
        downloading = _Setup([_one(1)], source=_source(Format.VIDEO_FILE), video_downloading=True)
        missing = _Setup([_one(1)], source=_source(Format.VIDEO_FILE))
        assert [
            s.kind_status(GenerationKind.MEDIA).videos_to_download
            for s in (downloaded, downloading, missing)
        ] == [0, 0, 1]
        assert missing.kind_status(GenerationKind.MEANING).videos_to_download == 0

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

    source_repo = MagicMock()
    source_repo.get_by_id.return_value = _source()
    cancelled = CancelGenerationUseCase(
        job_repo, SourceScopeResolver(source_repo, MagicMock()),
    ).execute(SCOPE, GenerationKind.TTS)

    assert cancelled == 3
    job_repo.cancel.assert_called_once_with(
        JobSelection(job_type=JobType.TTS, source_id=SOURCE_ID),
    )
