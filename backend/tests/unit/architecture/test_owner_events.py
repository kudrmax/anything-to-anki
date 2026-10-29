"""Every owner of a fact the card state is built from records what its writes change: a
write that records nothing leaves stored card state stale. Every public method of an owner
port is either a read or has a case here that runs it on its SQLAlchemy implementation."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import backend.infrastructure.persistence.models  # noqa: F401  registers every table on Base
import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.entities.card_report import CardReport
from backend.domain.entities.job import Job
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
from backend.domain.ports.candidate_meaning_image_repository import (
    CandidateMeaningImageRepository,
)
from backend.domain.ports.candidate_meaning_repository import CandidateMeaningRepository
from backend.domain.ports.candidate_media_repository import CandidateMediaRepository
from backend.domain.ports.candidate_pronunciation_repository import (
    CandidatePronunciationRepository,
)
from backend.domain.ports.candidate_repository import CandidateRepository
from backend.domain.ports.candidate_tts_repository import CandidateTTSRepository
from backend.domain.ports.card_report_repository import CardReportRepository
from backend.domain.ports.job_repository import JobRepository
from backend.domain.ports.occurrence_repository import OccurrenceRepository
from backend.domain.ports.settings_repository import SettingsRepository
from backend.domain.ports.source_repository import SourceRepository
from backend.domain.ports.word_mark_repository import WordMarkRepository
from backend.domain.ports.word_state_repository import WordStateRepository
from backend.domain.services.phrase_selection import SelectionChange
from backend.domain.services.rebuild_plan import (
    NewWord,
    OccurrenceInsert,
    OccurrenceRekey,
    OccurrenceScoreUpdate,
    OccurrenceTextUpdate,
    RebuildPlan,
    SectionChange,
    WordUpdate,
)
from backend.domain.value_objects.anki_binding import AnkiBinding
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_change import (
    BindingChanged,
    CardChange,
    CardContentChanged,
    DecisionChanged,
    LevelChanged,
    MarkChanged,
    PhraseChanged,
    SourceDeleted,
    WordContentChanged,
    WordsChanged,
)
from backend.domain.value_objects.card_choice import NoteKind
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.job_selection import JobSelection
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_status import SourceStatus
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_anki_sync_repository import SqlaAnkiSyncRepository
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_image_repository import (
    SqlaCandidateMeaningImageRepository,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_candidate_pronunciation_repository import (
    SqlaCandidatePronunciationRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_card_report_repository import (
    SqlaCardReportRepository,
)
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_settings_repository import SqlaSettingsRepository
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from backend.infrastructure.persistence.sqla_word_mark_repository import SqlaWordMarkRepository
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.decision_support import NOW
from tests.phrase_support import make_occurrence, phrase
from tests.rebuild_support import data, key_at, occ
from tests.word_support import bind, insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

OWNER_PORTS: tuple[type, ...] = (
    WordStateRepository,
    OccurrenceRepository,
    CandidateRepository,
    SourceRepository,
    WordMarkRepository,
    AnkiSyncRepository,
    SettingsRepository,
    CandidateMeaningRepository,
    CandidateMediaRepository,
    CandidateTTSRepository,
    CandidateClozeRepository,
    CandidatePronunciationRepository,
    CandidateMeaningImageRepository,
    JobRepository,
    CardReportRepository,
)

SOURCE = 1
OTHER_SOURCE = 2
LEVEL_KEY = "cefr_level"
SHARED_FILE = "/media/shared.mp3"

READ_ONLY: frozenset[tuple[str, str]] = frozenset({
    ("WordStateRepository", "of_word"),
    ("WordStateRepository", "of_source"),
    ("WordStateRepository", "of_words"),
    ("WordStateRepository", "of_lemma"),
    ("WordStateRepository", "of_lemmas"),
    # Defers what saves make stale to its end; the saves inside it record.
    ("WordStateRepository", "batch"),
    ("OccurrenceRepository", "by_source"),
    ("OccurrenceRepository", "projection"),
    ("OccurrenceRepository", "word_projection"),
    ("OccurrenceRepository", "get"),
    ("OccurrenceRepository", "of_ids"),
    ("OccurrenceRepository", "of_word"),
    ("OccurrenceRepository", "decision_phrases"),
    # Rewrites the revision with itself to take the write lock; nothing changes.
    ("OccurrenceRepository", "holds_revision"),
    ("OccurrenceRepository", "shown_by_word"),
    ("OccurrenceRepository", "word_rows"),
    ("OccurrenceRepository", "unsectioned"),
    ("CandidateRepository", "word_id"),
    ("CandidateRepository", "get_by_source"),
    ("CandidateRepository", "get_by_id"),
    ("CandidateRepository", "count_learning_in_anki"),
    ("CandidateRepository", "count_all"),
    ("CandidateRepository", "get_by_ids"),
    ("CandidateRepository", "get_lemma_map"),
    ("CandidateRepository", "chosen_to_learn"),
    ("CandidateRepository", "get_by_lemma"),
    ("CandidateRepository", "last_studied"),
    ("SourceRepository", "get_by_id"),
    ("SourceRepository", "list_all"),
    ("SourceRepository", "get_first_by_role"),
    ("SourceRepository", "get_title_map"),
    ("WordMarkRepository", "known_entries"),
    ("WordMarkRepository", "unknown_entries"),
    ("WordMarkRepository", "known_lemmas"),
    ("WordMarkRepository", "unknown_lemmas"),
    ("WordMarkRepository", "known_count"),
    ("WordMarkRepository", "unknown_count"),
    ("AnkiSyncRepository", "orphans"),
    ("SettingsRepository", "get"),
    ("CandidateMeaningRepository", "get_by_phrase_id"),
    ("CandidateMeaningRepository", "get_by_phrase_ids"),
    ("CandidateMediaRepository", "get_by_phrase_id"),
    ("CandidateMediaRepository", "get_by_phrase_ids"),
    ("CandidateMediaRepository", "get_all_by_source_id"),
    ("CandidateTTSRepository", "get_by_phrase_id"),
    ("CandidateTTSRepository", "get_by_phrase_ids"),
    ("CandidateClozeRepository", "get_by_phrase_id"),
    ("JobRepository", "still_claimed"),
    ("JobRepository", "get"),
    ("JobRepository", "has_active_jobs_for_source"),
    ("JobRepository", "sources_with_active_jobs"),
    ("JobRepository", "waiting_reason"),
    ("JobRepository", "get_queue_summary"),
    ("JobRepository", "get_jobs_for_phrases"),
    ("JobRepository", "get_jobs_for_candidates"),
    ("JobRepository", "get_jobs_by_status"),
    ("JobRepository", "get_failed_grouped_by_error"),
    ("CardReportRepository", "list_all"),
    ("CardReportRepository", "reported_phrase_ids"),
})


class Bench:
    """The owners on one database session, sharing the session's recorder."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.recorder = SessionChangeRecorder(session)
        self.word_states = SqlaWordStateRepository(session, self.recorder)
        self.occurrences = SqlaOccurrenceRepository(session, self.recorder)
        self.words = SqlaCandidateRepository(session, self.recorder)
        self.sources = SqlaSourceRepository(session, self.recorder)
        self.marks = SqlaWordMarkRepository(session, self.recorder)
        self.anki = SqlaAnkiSyncRepository(session, self.recorder)
        self.settings = SqlaSettingsRepository(session, self.recorder)
        self.meanings = SqlaCandidateMeaningRepository(session, self.recorder)
        self.media = SqlaCandidateMediaRepository(session, self.recorder)
        self.tts = SqlaCandidateTTSRepository(session, self.recorder)
        self.clozes = SqlaCandidateClozeRepository(session, self.recorder)
        self.pronunciations = SqlaCandidatePronunciationRepository(session, self.recorder)
        self.images = SqlaCandidateMeaningImageRepository(session, self.recorder)
        self.jobs = SqlaJobRepository(session, self.recorder)
        self.reports = SqlaCardReportRepository(session, self.recorder)

    def word(self, word_id: int, lemma: str, *, source_id: int = SOURCE) -> int:
        """A word with one shown phrase, written straight to the tables; returns the
        phrase id."""
        insert_word(self.session, word_id, source_id=source_id, lemma=lemma)
        return phrase_id_of(word_id)

    def ready(self) -> None:
        """What the arrangement recorded is dropped: only the call under test counts."""
        self.session.flush()
        self.recorder.drain()


type Expected = set[CardChange]


@dataclass(frozen=True)
class WriteCase:
    """Arranges, calls the method and returns the changes it must record, exactly."""

    run: Callable[[Bench], Expected]


def _word_state_save(b: Bench) -> Expected:
    b.word(1, "Glare")
    state = b.word_states.of_word(1)
    assert state is not None
    b.ready()
    b.word_states.save(state)
    return {DecisionChanged("glare")}


def _occurrence_add(b: Bench) -> Expected:
    b.word(1, "glare")
    b.ready()
    added = b.occurrences.add(make_occurrence(candidate_id=1))
    assert added.id is not None
    return {PhraseChanged(added.id)}


def _occurrence_write_text(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.occurrences.write_text(
        phrase_id, phrase("She glared back.", "glared"), None,
        earned_section=CandidateSection.EXTRA,
    )
    return {PhraseChanged(phrase_id), CardContentChanged(phrase_id)}


def _occurrence_set_key(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.occurrences.set_key(phrase_id, OccurrenceKey(block=0, line=3, char=0))
    return {PhraseChanged(phrase_id)}


def _occurrence_set_shown(b: Bench) -> Expected:
    first, second = b.word(1, "glare"), b.word(2, "stare")
    b.ready()
    b.occurrences.set_shown([first, second], None)
    return {PhraseChanged(first), PhraseChanged(second)}


def _occurrence_set_replaces_selection(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.occurrences.set_replaces_selection(phrase_id, True)
    return {PhraseChanged(phrase_id)}


def _occurrence_remove_card(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.occurrences.remove_card(phrase_id)
    return {PhraseChanged(phrase_id)}


def _occurrence_set_earned_sections(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.occurrences.set_earned_sections([SectionChange(phrase_id, CandidateSection.EXTRA)])
    return {PhraseChanged(phrase_id)}


def _occurrence_apply_plan(b: Bench) -> Expected:
    """One phrase per kind of write, so each kind shows on its own."""
    deleted = b.word(1, "doomed")
    rewritten = b.word(2, "glare")
    rekeyed = b.word(3, "stare")
    rescored = b.word(4, "gaze")
    unselected = b.word(5, "peek")
    restamped = b.word(6, "blink")
    rewrite = "She glared back."
    b.ready()
    applied = b.occurrences.apply_plan(RebuildPlan(
        source_id=SOURCE,
        words_to_create=(NewWord("Linger", False, data()),),
        words_to_update=(WordUpdate(2, data(zipf=4.0)),),
        words_to_delete=(1,),
        occ_to_insert=(OccurrenceInsert(
            WordKey.of("linger", False), occ(7), shown=True,
            earned_section=CandidateSection.READY,
        ),),
        occ_to_update_text=(OccurrenceTextUpdate(
            occurrence_id=rewritten, phrase=phrase(rewrite, "glared"),
            phrase_position=occ(2, text=rewrite).phrase_position, fragment_score=10.0,
            bump_revision=True, drop_text_generation=True,
            earned_section=CandidateSection.READY,
        ),),
        occ_to_update_score=(OccurrenceScoreUpdate(rescored, 20.0),),
        occ_to_rekey=(OccurrenceRekey(rekeyed, key_at(9)),),
        occ_to_delete=(deleted,),
        selection_changes=(SelectionChange(clear_selection=(unselected,)),),
        section_changes=(SectionChange(restamped, CandidateSection.EXTRA),),
    ))
    (inserted,) = applied.inserted
    return {
        WordsChanged(SOURCE, frozenset({"doomed", "glare", "linger"})),
        CardContentChanged(rewritten),
        WordContentChanged(2),
        *(
            PhraseChanged(phrase_id)
            for phrase_id in (deleted, rewritten, rekeyed, rescored, unselected, restamped,
                              inserted)
        ),
    }


def _candidate_add_word(b: Bench) -> Expected:
    b.ready()
    b.words.add_word(StoredCandidate(
        source_id=SOURCE, lemma="Glare", pos="VERB", cefr_level=None, zipf_frequency=3.0,
        occurrences=1, status=WordStatus.NEW,
    ))
    return {WordsChanged(SOURCE, frozenset({"glare"}))}


def _candidate_set_studied_at(b: Bench) -> Expected:
    b.word(1, "Glare")
    b.ready()
    b.words.set_studied_at(1, NOW)
    return {WordsChanged(SOURCE, frozenset({"glare"}))}


def _candidate_delete_by_source(b: Bench) -> Expected:
    b.word(1, "glare")
    b.word(2, "stare")
    b.word(3, "gaze", source_id=OTHER_SOURCE)
    b.ready()
    b.words.delete_by_source(SOURCE)
    return {SourceDeleted(SOURCE, frozenset({"glare", "stare"}))}


def _source_delete(b: Bench) -> Expected:
    b.word(1, "glare")
    b.word(2, "stare")
    b.ready()
    b.sources.delete(SOURCE)
    return {SourceDeleted(SOURCE, frozenset({"glare", "stare"}))}


def _source_create(b: Bench) -> Expected:
    b.ready()
    b.sources.create(Source(status=SourceStatus.NEW, title="New"))
    return set()


def _source_update_status(b: Bench) -> Expected:
    b.ready()
    b.sources.update_status(SOURCE, SourceStatus.ERROR, error_message="broken")
    return set()


def _source_update_title(b: Bench) -> Expected:
    b.ready()
    b.sources.update_title(SOURCE, "Renamed")
    return set()


def _source_update_video_path(b: Bench) -> Expected:
    b.ready()
    b.sources.update_video_path(SOURCE, "/video.mp4")
    return set()


def _source_set_collections(b: Bench) -> Expected:
    b.ready()
    b.sources.set_collections({SOURCE: None})
    return set()


def _mark_known(b: Bench) -> Expected:
    b.ready()
    b.marks.mark_known("Glare", "VERB")
    return {MarkChanged("glare")}


def _mark_unknown(b: Bench) -> Expected:
    b.ready()
    b.marks.mark_unknown("Glare")
    return {MarkChanged("glare")}


def _remove_known_entry(b: Bench) -> Expected:
    b.marks.mark_known("glare", "VERB")
    b.marks.mark_known("glare", "NOUN")
    b.ready()
    b.marks.remove_known_entry("glare", "VERB")
    return {MarkChanged("glare")}


def _remove_known(b: Bench) -> Expected:
    b.marks.mark_known("glare", "VERB")
    b.marks.mark_known("glare", "NOUN")
    b.ready()
    b.marks.remove_known("Glare")
    return {MarkChanged("glare")}


def _remove_unknown(b: Bench) -> Expected:
    b.marks.mark_unknown("glare")
    b.ready()
    b.marks.remove_unknown("Glare")
    return {MarkChanged("glare")}


def _anki_bind(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.anki.bind(AnkiBinding(
        word_id=1, phrase_id=phrase_id, note_id=900, lemma="Glare", pos="VERB",
        note_kind=NoteKind.LEARN, learning_since=NOW,
    ))
    return {BindingChanged("glare")}


def _anki_release(b: Bench) -> Expected:
    first, second = b.word(1, "glare"), b.word(2, "stare")
    bind(b.session, 1, first, note_id=901)
    bind(b.session, 2, second, note_id=902)
    b.ready()
    b.anki.release([first], NOW)
    return {BindingChanged("glare")}


def _anki_release_rows(b: Bench) -> Expected:
    first, second = b.word(1, "glare"), b.word(2, "stare")
    bind(b.session, 1, first, note_id=901)
    bind(b.session, 2, second, note_id=902)
    binding_id = b.session.execute(
        text("SELECT id FROM anki_synced_cards WHERE phrase_id = :p"), {"p": second},
    ).scalar_one()
    b.ready()
    b.anki.release_rows([binding_id], NOW)
    return {BindingChanged("stare")}


def _anki_orphan(b: Bench) -> Expected:
    first, second = b.word(1, "glare"), b.word(2, "stare")
    bind(b.session, 1, first, note_id=901)
    bind(b.session, 2, second, note_id=902)
    b.ready()
    b.anki.orphan([first])
    return {BindingChanged("glare")}


def _anki_orphan_source(b: Bench) -> Expected:
    first = b.word(1, "glare")
    other = b.word(2, "stare", source_id=OTHER_SOURCE)
    bind(b.session, 1, first, note_id=901)
    bind(b.session, 2, other, note_id=902)
    b.ready()
    b.anki.orphan_source(SOURCE)
    return {BindingChanged("glare")}


def _settings_set(b: Bench) -> Expected:
    b.ready()
    b.settings.set(LEVEL_KEY, "B2")
    return {LevelChanged()}


def _meaning(word_id: int, *, ipa: str | None = None) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=word_id, meaning="to stare angrily", translation=None, synonyms=None,
        examples=None, ipa=ipa, generated_at=None,
    )


def _meaning_upsert(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.meanings.upsert_for_phrase(phrase_id, _meaning(1, ipa="ɡleə"))
    return {CardContentChanged(phrase_id), WordContentChanged(1)}


def _meaning_delete(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.meanings.upsert_for_phrase(phrase_id, _meaning(1))
    b.ready()
    b.meanings.delete_by_phrase_id(phrase_id)
    return {CardContentChanged(phrase_id)}


def _media(word_id: int, *, audio: str | None = None) -> CandidateMedia:
    return CandidateMedia(
        candidate_id=word_id, screenshot_path="/media/shot.jpg", audio_path=audio,
        start_ms=0, end_ms=1000, generated_at=NOW,
    )


def _media_upsert(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.media.upsert_for_phrase(phrase_id, _media(1))
    return {CardContentChanged(phrase_id)}


def _media_clear_phrase_paths(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.media.upsert_for_phrase(phrase_id, _media(1))
    b.ready()
    b.media.clear_phrase_paths(phrase_id, clear_screenshot=True, clear_audio=False)
    return {CardContentChanged(phrase_id)}


def _media_clear_missing_file(b: Bench) -> Expected:
    first, second, untouched = b.word(1, "glare"), b.word(2, "stare"), b.word(3, "gaze")
    b.media.upsert_for_phrase(first, _media(1, audio=SHARED_FILE))
    b.media.upsert_for_phrase(second, replace(_media(2), screenshot_path=SHARED_FILE))
    b.media.upsert_for_phrase(untouched, _media(3))
    b.ready()
    b.media.clear_missing_file(SHARED_FILE)
    return {CardContentChanged(first), CardContentChanged(second)}


def _media_set_timecodes(b: Bench) -> Expected:
    timed, untimed = b.word(1, "glare"), b.word(2, "stare")
    b.ready()
    b.media.set_timecodes({timed: (0, 1000), untimed: None})
    return {CardContentChanged(timed), CardContentChanged(untimed)}


def _tts_upsert(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.tts.upsert_for_phrase(phrase_id, CandidateTTS(1, "/media/tts.mp3", NOW))
    return {CardContentChanged(phrase_id)}


def _tts_delete(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.tts.upsert_for_phrase(phrase_id, CandidateTTS(1, "/media/tts.mp3", NOW))
    b.ready()
    b.tts.delete_by_phrase_id(phrase_id)
    return {CardContentChanged(phrase_id)}


def _cloze(word_id: int) -> CandidateCloze:
    return CandidateCloze(word_id, (0,), ClozeHintKind.NONE, None, "glare")


def _cloze_upsert(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.clozes.upsert_for_phrase(phrase_id, _cloze(1))
    return {CardContentChanged(phrase_id)}


def _cloze_delete(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.clozes.upsert_for_phrase(phrase_id, _cloze(1))
    b.ready()
    b.clozes.delete_by_phrase_id(phrase_id)
    return {CardContentChanged(phrase_id)}


def _pronunciation_upsert(b: Bench) -> Expected:
    b.word(1, "glare")
    b.ready()
    b.pronunciations.upsert(CandidatePronunciation(1, "/media/us.mp3", None, NOW))
    return {WordContentChanged(1)}


def _image_upsert(b: Bench) -> Expected:
    b.word(1, "glare")
    b.ready()
    b.images.upsert(CandidateMeaningImage(1, "/media/glare.jpg"))
    return {WordContentChanged(1)}


def _image_delete(b: Bench) -> Expected:
    b.word(1, "glare")
    b.images.upsert(CandidateMeaningImage(1, "/media/glare.jpg"))
    b.ready()
    b.images.delete_by_candidate_id(1)
    return {WordContentChanged(1)}


def _phrase_job(phrase_id: int, word_id: int = 1) -> Job:
    return Job.queued(JobType.MEANING, SOURCE, word_id, phrase_id=phrase_id, phrase_revision=0)


def _word_job(word_id: int) -> Job:
    return Job.queued(JobType.PRONUNCIATION, SOURCE, word_id)


def _queued(b: Bench, *jobs: Job) -> list[Job]:
    """The jobs queued and running: the arrangement's changes dropped."""
    queued = b.jobs.enqueue(list(jobs))
    b.ready()
    return queued


def _running(b: Bench, *jobs: Job) -> list[Job]:
    _queued(b, *jobs)
    running = b.jobs.claim_next_run({}, None, frozenset(JobType))
    b.ready()
    return running


def _job_enqueue(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.word(2, "stare")
    b.ready()
    b.jobs.enqueue([_phrase_job(phrase_id), _word_job(2)])
    return {CardContentChanged(phrase_id), WordContentChanged(2)}


def _job_claim_next_run(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    _queued(b, _phrase_job(phrase_id))
    b.jobs.claim_next_run({})
    return {CardContentChanged(phrase_id)}


def _job_complete(b: Bench) -> Expected:
    b.word(1, "glare")
    b.jobs.complete(_running(b, _word_job(1)))
    return {WordContentChanged(1)}


def _job_fail(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    [job] = _running(b, _phrase_job(phrase_id))
    assert job.id is not None
    b.jobs.fail([job.id], "boom")
    return {CardContentChanged(phrase_id)}


def _job_requeue(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    [job] = _running(b, _phrase_job(phrase_id))
    assert job.id is not None
    b.jobs.requeue([job.id], "Blocked country: RU. Turn on VPN.")
    return {CardContentChanged(phrase_id)}


def _job_requeue_running(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    _running(b, _phrase_job(phrase_id))
    b.jobs.requeue_running()
    return {CardContentChanged(phrase_id)}


def _job_fail_running(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    _running(b, _phrase_job(phrase_id))
    b.jobs.fail_running(JobType.MEANING, "boom")
    return {CardContentChanged(phrase_id)}


def _job_cancel(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.word(2, "stare")
    _queued(b, _phrase_job(phrase_id), _word_job(2))
    b.jobs.cancel(JobSelection(job_type=JobType.PRONUNCIATION))
    return {WordContentChanged(2)}


def _job_cancel_for_phrases(b: Bench) -> Expected:
    first, second = b.word(1, "glare"), b.word(2, "stare")
    _queued(b, _phrase_job(first), _phrase_job(second, 2))
    b.jobs.cancel_for_phrases([first])
    return {CardContentChanged(first)}


def _failed(b: Bench, job: Job) -> None:
    [running] = _running(b, job)
    assert running.id is not None
    b.jobs.fail([running.id], "boom")
    b.ready()


def _job_dismiss(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    _failed(b, _phrase_job(phrase_id))
    b.jobs.dismiss(JobSelection())
    return {CardContentChanged(phrase_id)}


def _job_retry(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    _failed(b, _phrase_job(phrase_id))
    b.jobs.retry(JobSelection())
    return {CardContentChanged(phrase_id)}


def _report_add(b: Bench) -> Expected:
    phrase_id = b.word(1, "glare")
    b.ready()
    b.reports.add(CardReport(
        source_id=SOURCE, source_title="title", candidate_id=1, lemma="glare",
        surface_form=None, context_fragment="She glared.", zipf_frequency=3.0,
        cefr_level=None, fragment_unknown_count=0, is_phrasal_verb=False, reasons=(),
        comment="odd", phrase_id=phrase_id,
    ))
    return {CardContentChanged(phrase_id)}


WRITE_CASES: dict[tuple[str, str], WriteCase] = {
    ("WordStateRepository", "save"): WriteCase(_word_state_save),
    ("OccurrenceRepository", "add"): WriteCase(_occurrence_add),
    ("OccurrenceRepository", "write_text"): WriteCase(_occurrence_write_text),
    ("OccurrenceRepository", "set_key"): WriteCase(_occurrence_set_key),
    ("OccurrenceRepository", "set_shown"): WriteCase(_occurrence_set_shown),
    ("OccurrenceRepository", "set_replaces_selection"): WriteCase(
        _occurrence_set_replaces_selection,
    ),
    ("OccurrenceRepository", "remove_card"): WriteCase(_occurrence_remove_card),
    ("OccurrenceRepository", "set_earned_sections"): WriteCase(_occurrence_set_earned_sections),
    ("OccurrenceRepository", "apply_plan"): WriteCase(_occurrence_apply_plan),
    ("CandidateRepository", "add_word"): WriteCase(_candidate_add_word),
    ("CandidateRepository", "set_studied_at"): WriteCase(_candidate_set_studied_at),
    ("CandidateRepository", "delete_by_source"): WriteCase(_candidate_delete_by_source),
    ("SourceRepository", "delete"): WriteCase(_source_delete),
    # The source's own row: no card fact lives there.
    ("SourceRepository", "create"): WriteCase(_source_create),
    ("SourceRepository", "update_status"): WriteCase(_source_update_status),
    ("SourceRepository", "update_title"): WriteCase(_source_update_title),
    ("SourceRepository", "update_video_path"): WriteCase(_source_update_video_path),
    ("SourceRepository", "set_collections"): WriteCase(_source_set_collections),
    ("WordMarkRepository", "mark_known"): WriteCase(_mark_known),
    ("WordMarkRepository", "mark_unknown"): WriteCase(_mark_unknown),
    ("WordMarkRepository", "remove_known_entry"): WriteCase(_remove_known_entry),
    ("WordMarkRepository", "remove_known"): WriteCase(_remove_known),
    ("WordMarkRepository", "remove_unknown"): WriteCase(_remove_unknown),
    ("AnkiSyncRepository", "bind"): WriteCase(_anki_bind),
    ("AnkiSyncRepository", "release"): WriteCase(_anki_release),
    ("AnkiSyncRepository", "release_rows"): WriteCase(_anki_release_rows),
    ("AnkiSyncRepository", "orphan"): WriteCase(_anki_orphan),
    ("AnkiSyncRepository", "orphan_source"): WriteCase(_anki_orphan_source),
    ("SettingsRepository", "set"): WriteCase(_settings_set),
    ("CandidateMeaningRepository", "upsert_for_phrase"): WriteCase(_meaning_upsert),
    ("CandidateMeaningRepository", "delete_by_phrase_id"): WriteCase(_meaning_delete),
    ("CandidateMediaRepository", "upsert_for_phrase"): WriteCase(_media_upsert),
    ("CandidateMediaRepository", "clear_phrase_paths"): WriteCase(_media_clear_phrase_paths),
    ("CandidateMediaRepository", "clear_missing_file"): WriteCase(_media_clear_missing_file),
    ("CandidateMediaRepository", "set_timecodes"): WriteCase(_media_set_timecodes),
    ("CandidateTTSRepository", "upsert_for_phrase"): WriteCase(_tts_upsert),
    ("CandidateTTSRepository", "delete_by_phrase_id"): WriteCase(_tts_delete),
    ("CandidateClozeRepository", "upsert_for_phrase"): WriteCase(_cloze_upsert),
    ("CandidateClozeRepository", "delete_by_phrase_id"): WriteCase(_cloze_delete),
    ("CandidatePronunciationRepository", "upsert"): WriteCase(_pronunciation_upsert),
    ("CandidateMeaningImageRepository", "upsert"): WriteCase(_image_upsert),
    ("CandidateMeaningImageRepository", "delete_by_candidate_id"): WriteCase(_image_delete),
    ("JobRepository", "enqueue"): WriteCase(_job_enqueue),
    ("JobRepository", "claim_next_run"): WriteCase(_job_claim_next_run),
    ("JobRepository", "complete"): WriteCase(_job_complete),
    ("JobRepository", "fail"): WriteCase(_job_fail),
    ("JobRepository", "requeue"): WriteCase(_job_requeue),
    ("JobRepository", "requeue_running"): WriteCase(_job_requeue_running),
    ("JobRepository", "fail_running"): WriteCase(_job_fail_running),
    ("JobRepository", "cancel"): WriteCase(_job_cancel),
    ("JobRepository", "cancel_for_phrases"): WriteCase(_job_cancel_for_phrases),
    ("JobRepository", "dismiss"): WriteCase(_job_dismiss),
    ("JobRepository", "retry"): WriteCase(_job_retry),
    ("CardReportRepository", "add"): WriteCase(_report_add),
}


def _public_methods() -> set[tuple[str, str]]:
    return {
        (port.__name__, name)
        for port in OWNER_PORTS
        for name, member in vars(port).items()
        if callable(member) and not name.startswith("_")
    }


@pytest.fixture()
def bench(tmp_path: Path) -> Iterator[Bench]:
    engine = create_engine(f"sqlite:///{tmp_path / 'owners.db'}")
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        for source_id in (SOURCE, OTHER_SOURCE):
            session.execute(
                text(
                    "INSERT INTO sources (id, title, status, created_at)"
                    " VALUES (:id, 'title', 'done', '2026-01-01 00:00:00')"
                ),
                {"id": source_id},
            )
        yield Bench(session)
    engine.dispose()


def test_every_public_method_of_an_owner_is_a_read_or_has_a_write_case() -> None:
    unclassified = _public_methods() - READ_ONLY - set(WRITE_CASES)

    assert not unclassified, (
        "Owner methods neither in READ_ONLY nor in WRITE_CASES: a write must record what it"
        f" changes. Classify them: {sorted(unclassified)}"
    )


def test_the_lists_name_only_existing_methods_and_each_once() -> None:
    assert not READ_ONLY & set(WRITE_CASES)
    assert (READ_ONLY | set(WRITE_CASES)) <= _public_methods()


@pytest.mark.parametrize("method", sorted(WRITE_CASES), ids=lambda m: ".".join(m))
def test_a_write_records_exactly_what_it_changed(bench: Bench, method: tuple[str, str]) -> None:
    expected = WRITE_CASES[method].run(bench)

    assert set(bench.recorder.drain()) == expected


def test_a_setting_other_than_the_level_records_nothing(bench: Bench) -> None:
    bench.settings.set("naming_rule", "{{title}}")

    assert bench.recorder.drain() == ()


def test_a_remove_that_finds_nothing_records_nothing(bench: Bench) -> None:
    bench.marks.remove_known_entry("glare", None)
    bench.marks.remove_known("glare")
    bench.marks.remove_unknown("glare")

    assert bench.recorder.drain() == ()


def test_deleting_a_source_without_words_records_nothing(bench: Bench) -> None:
    bench.sources.delete(OTHER_SOURCE)

    assert bench.recorder.drain() == ()
