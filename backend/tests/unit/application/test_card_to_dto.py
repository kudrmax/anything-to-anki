"""Tests for card_to_dto: a card of the review list as the API shows it."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.application.dto.source_dtos import CardJobs, ShownDTO, ShownStatus, card_to_dto
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.job import Job
from backend.domain.services.card_view import Command, ShownTone, Where
from backend.domain.value_objects.card_choice import Binding, CardChoice, NoteKind, Press, Refusal
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.job_status import JobStatus
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_origin_kind import DecisionKind
from backend.domain.value_objects.word_status import WordStatus

from tests.card_support import card, occurrence, word
from tests.decision_support import NOW as REQUEST_NOW
from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.review_card import ReviewCard

NOW = datetime(2025, 1, 1, tzinfo=UTC)
WORD_JOB_TYPES = (JobType.PRONUNCIATION,)


def _make_candidate(
    *,
    cid: int = 1,
    meaning: CandidateMeaning | None = None,
    media: CandidateMedia | None = None,
    pronunciation: CandidatePronunciation | None = None,
) -> ReviewCard:
    return card(
        word(cid, pronunciation=pronunciation),
        occurrence(cid, cid, meaning=meaning, media=media),
    )


def _make_job(
    *,
    job_type: JobType,
    status: JobStatus = JobStatus.QUEUED,
    error: str | None = None,
    candidate_id: int = 1,
    job_id: int = 100,
) -> Job:
    return Job(
        id=job_id,
        job_type=job_type,
        candidate_id=candidate_id,
        source_id=10,
        status=status,
        error=error,
        created_at=NOW,
        started_at=None,
        phrase_id=None if job_type in WORD_JOB_TYPES else candidate_id,
    )


def _jobs_dict(jobs: list[Job]) -> CardJobs:
    phrases: dict[int, dict[str, Job]] = {}
    words: dict[int, dict[str, Job]] = {}
    for j in jobs:
        if j.phrase_id is not None:
            phrases.setdefault(j.phrase_id, {})[j.job_type.value] = j
        elif j.candidate_id is not None:
            words.setdefault(j.candidate_id, {})[j.job_type.value] = j
    return CardJobs(of_phrases=phrases, of_words=words)


@pytest.mark.unit
class TestCardToDtoStatusDerivation:
    """Test all branches of status derivation in card_to_dto."""

    # --- No jobs, no enrichment data ---

    def test_no_jobs_no_enrichment_data(self) -> None:
        c = _make_candidate()
        dto = card_to_dto(c)
        assert dto.meaning is None
        assert dto.media is None
        assert dto.pronunciation is None

    # --- No jobs, enrichment data exists ---

    def test_no_jobs_meaning_data_exists(self) -> None:
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation="тест",
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        c = _make_candidate(meaning=meaning)
        dto = card_to_dto(c)
        assert dto.meaning is not None
        assert dto.meaning.status == "done"
        assert dto.meaning.error is None

    def test_no_jobs_media_with_screenshot(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path="/img.png", audio_path=None,
            start_ms=None, end_ms=None, generated_at=NOW,
        )
        c = _make_candidate(media=media)
        dto = card_to_dto(c)
        assert dto.media is not None
        assert dto.media.status == "done"

    def test_no_jobs_media_with_timecodes_no_screenshot(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path=None, audio_path=None,
            start_ms=1000, end_ms=5000, generated_at=None,
        )
        c = _make_candidate(media=media)
        dto = card_to_dto(c)
        assert dto.media is not None
        assert dto.media.status == "idle"

    def test_no_jobs_pronunciation_with_audio(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=1, us_audio_path="/us.mp3", uk_audio_path=None,
            generated_at=NOW,
        )
        c = _make_candidate(pronunciation=pron)
        dto = card_to_dto(c)
        assert dto.pronunciation is not None
        assert dto.pronunciation.status == "done"

    # --- Jobs exist, no enrichment data ---

    def test_meaning_job_queued_no_data(self) -> None:
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.QUEUED)
        c = _make_candidate()
        dto = card_to_dto(c, _jobs_dict([job]))
        assert dto.meaning is not None
        assert dto.meaning.status == "queued"
        assert dto.meaning.meaning is None

    def test_meaning_job_running_no_data(self) -> None:
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.RUNNING)
        c = _make_candidate()
        dto = card_to_dto(c, _jobs_dict([job]))
        assert dto.meaning is not None
        assert dto.meaning.status == "running"

    def test_meaning_job_failed_with_error_no_data(self) -> None:
        job = _make_job(
            job_type=JobType.MEANING, status=JobStatus.FAILED,
            error="AI service unavailable",
        )
        c = _make_candidate()
        dto = card_to_dto(c, _jobs_dict([job]))
        assert dto.meaning is not None
        assert dto.meaning.status == "failed"
        assert dto.meaning.error == "AI service unavailable"

    def test_media_job_queued_no_data(self) -> None:
        job = _make_job(job_type=JobType.MEDIA, status=JobStatus.QUEUED)
        c = _make_candidate()
        dto = card_to_dto(c, _jobs_dict([job]))
        assert dto.media is not None
        assert dto.media.status == "queued"
        assert dto.media.screenshot_path is None

    def test_pronunciation_job_running_no_data(self) -> None:
        job = _make_job(job_type=JobType.PRONUNCIATION, status=JobStatus.RUNNING)
        c = _make_candidate()
        dto = card_to_dto(c, _jobs_dict([job]))
        assert dto.pronunciation is not None
        assert dto.pronunciation.status == "running"

    # --- Jobs exist, enrichment data also exists (job overrides) ---

    def test_meaning_job_overrides_data_status(self) -> None:
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation="тест",
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.RUNNING)
        c = _make_candidate(meaning=meaning)
        dto = card_to_dto(c, _jobs_dict([job]))
        assert dto.meaning is not None
        # Job status overrides "done" from existing data
        assert dto.meaning.status == "running"

    def test_media_job_overrides_data_status(self) -> None:
        media = CandidateMedia(
            candidate_id=1, screenshot_path="/img.png", audio_path=None,
            start_ms=None, end_ms=None, generated_at=NOW,
        )
        job = _make_job(job_type=JobType.MEDIA, status=JobStatus.FAILED, error="timeout")
        c = _make_candidate(media=media)
        dto = card_to_dto(c, _jobs_dict([job]))
        assert dto.media is not None
        assert dto.media.status == "failed"
        assert dto.media.error == "timeout"

    def test_pronunciation_job_overrides_data_status(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=1, us_audio_path="/us.mp3", uk_audio_path=None,
            generated_at=NOW,
        )
        job = _make_job(job_type=JobType.PRONUNCIATION, status=JobStatus.QUEUED)
        c = _make_candidate(pronunciation=pron)
        dto = card_to_dto(c, _jobs_dict([job]))
        assert dto.pronunciation is not None
        assert dto.pronunciation.status == "queued"

    # --- Multiple job types for same candidate ---

    def test_multiple_job_types_each_gets_own_status(self) -> None:
        meaning_job = _make_job(
            job_type=JobType.MEANING, status=JobStatus.RUNNING, job_id=100,
        )
        media_job = _make_job(
            job_type=JobType.MEDIA, status=JobStatus.QUEUED, job_id=101,
        )
        pron_job = _make_job(
            job_type=JobType.PRONUNCIATION, status=JobStatus.FAILED,
            error="not found", job_id=102,
        )
        c = _make_candidate()
        dto = card_to_dto(c, _jobs_dict([meaning_job, media_job, pron_job]))
        assert dto.meaning is not None
        assert dto.meaning.status == "running"
        assert dto.media is not None
        assert dto.media.status == "queued"
        assert dto.pronunciation is not None
        assert dto.pronunciation.status == "failed"
        assert dto.pronunciation.error == "not found"

    # --- Empty jobs dict (no jobs for this candidate) ---

    def test_empty_jobs_dict_with_data(self) -> None:
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation=None,
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        c = _make_candidate(meaning=meaning)
        dto = card_to_dto(c, CardJobs())
        assert dto.meaning is not None
        assert dto.meaning.status == "done"

    def test_jobs_for_different_candidate_ignored(self) -> None:
        """Jobs for a different candidate_id don't affect this candidate's DTO."""
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation=None,
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        c = _make_candidate(cid=1, meaning=meaning)
        # Job belongs to candidate_id=999, not 1
        job = _make_job(
            job_type=JobType.MEANING, status=JobStatus.RUNNING, candidate_id=999,
        )
        dto = card_to_dto(c, _jobs_dict([job]))
        # No matching job for candidate 1 → status from data
        assert dto.meaning is not None
        assert dto.meaning.status == "done"


@pytest.mark.unit
class TestCardToDtoCloze:
    TEXT = "She finally gave up smoking."

    def _card(
        self, cloze: CandidateCloze | None, choice: CardChoice = CardChoice.CLOZE,
        *, exported: bool = False,
    ) -> ReviewCard:
        status = (
            WordStatus.KNOWN if choice is CardChoice.KNOWN
            else WordStatus.LEARNING if exported else WordStatus.LEARN
        )
        return card(
            word(1, "give up", status=status),
            occurrence(
                1, 1, phrase(self.TEXT, "give up", lemmas={"gave": "give"}), cloze=cloze,
                choice=choice,
                binding=Binding(NoteKind.CLOZE, REQUEST_NOW) if exported else None,
            ),
        )

    def test_a_cloze_card_has_its_effective_cloze_and_can_edit_cloze(self) -> None:
        stale = CandidateCloze(1, (0,), ClozeHintKind.FIRST_LETTER, None, "Old phrase.")
        dto = card_to_dto(self._card(stale))
        assert dto.cloze is not None
        assert dto.cloze.hidden_word_indices == [2, 3]
        assert dto.cloze.hint_kind == "first_letter"
        assert dto.cloze.custom_hint is None
        assert dto.can_edit_cloze is True

    def test_a_cloze_in_anki_shows_its_cloze_and_cannot_change_it(self) -> None:
        cloze = CandidateCloze(1, (2, 3), ClozeHintKind.NONE, None, self.TEXT)
        exported = card_to_dto(self._card(cloze, exported=True))
        assert exported.cloze is not None
        assert exported.can_edit_cloze is False
        cloze_button = next(b for b in exported.state.buttons if b.button is Press.CLOZE)
        # P17: Cloze on a cloze in Anki undoes it; the markup stays as Anki holds it.
        assert (cloze_button.command, cloze_button.pressed) == (Command.DECIDE, True)

    def test_markup_kept_on_a_card_that_is_no_cloze_now_is_not_shown(self) -> None:
        cloze = CandidateCloze(1, (2, 3), ClozeHintKind.NONE, None, self.TEXT)
        assert card_to_dto(self._card(cloze, CardChoice.KNOWN)).cloze is None
        assert card_to_dto(self._card(cloze, CardChoice.LEARN)).cloze is None
        assert card_to_dto(self._card(cloze, CardChoice.NONE)).cloze is None


@pytest.mark.unit
class TestCardToDtoDecision:
    def test_a_card_carries_its_phrase_and_its_word(self) -> None:
        dto = card_to_dto(card(word(7), occurrence(42, 7)))
        assert (dto.phrase_id, dto.word_id) == (42, 7)

    def test_the_word_decision_beats_a_skip_of_the_phrase(self) -> None:
        skipped = occurrence(1, 1, skipped=True)
        assert card_to_dto(card(word(), skipped)).shown == ShownDTO(
            status=ShownStatus.NEW, skipped=True, where=Where.NOWHERE, tone=ShownTone.SETTLED,
        )
        learned = card_to_dto(card(word(status=WordStatus.LEARN), skipped))
        assert (
            learned.choice, learned.shown.status, learned.shown.skipped, learned.shown.tone,
        ) == (CardChoice.SKIP, ShownStatus.LEARN, True, ShownTone.LEARNING)

    def test_a_card_done_elsewhere_says_why(self) -> None:
        dto = card_to_dto(card(elsewhere=ElsewhereStatus.LEARNING))
        assert (dto.shown.status, dto.shown.where) == (ShownStatus.LEARNING, Where.OTHER_SOURCE)
        learn = next(b for b in dto.state.buttons if b.button is Press.LEARN)
        assert (learn.command, learn.refused) == (None, Refusal.DECIDED_ELSEWHERE)
        assert dto.is_done is True

    def test_the_decision_card_and_its_kind(self) -> None:
        decided = occurrence(1, 1, is_decision=True, decision_kind=DecisionKind.LEARN)
        dto = card_to_dto(card(word(status=WordStatus.LEARN), decided))
        assert dto.choice is CardChoice.LEARN
        assert dto.shown.where is Where.HERE
        assert [(b.button, b.command, b.pressed) for b in dto.state.buttons][0] == (
            Press.LEARN, Command.DECIDE, True,
        )

    def test_jobs_of_another_phrase_of_the_word_are_not_this_cards(self) -> None:
        job = replace(_make_job(job_type=JobType.POLISH), phrase_id=2)
        assert card_to_dto(card(), _jobs_dict([job])).polish_status is None
        other = card_to_dto(card(word(), occurrence(2, 1)), _jobs_dict([job]))
        assert other.polish_status == "queued"


@pytest.mark.unit
class TestMeaningAction:
    """What a card offers about its meaning; the web shows it as is."""

    def test_a_card_without_a_meaning_offers_generation(self) -> None:
        assert card_to_dto(_make_candidate()).meaning_action == "generate"

    def test_a_queued_meaning_still_offers_generation(self) -> None:
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.QUEUED)
        assert card_to_dto(_make_candidate(), _jobs_dict([job])).meaning_action == "generate"

    def test_a_failed_meaning_offers_a_retry(self) -> None:
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.FAILED, error="boom")
        assert card_to_dto(_make_candidate(), _jobs_dict([job])).meaning_action == "retry"

    def test_nothing_while_the_meaning_is_being_made(self) -> None:
        job = _make_job(job_type=JobType.MEANING, status=JobStatus.RUNNING)
        assert card_to_dto(_make_candidate(), _jobs_dict([job])).meaning_action is None

    def test_nothing_once_the_meaning_is_there(self) -> None:
        meaning = CandidateMeaning(
            candidate_id=1, meaning="a test", translation=None,
            synonyms=None, examples=None, ipa=None, generated_at=NOW,
        )
        assert card_to_dto(_make_candidate(meaning=meaning)).meaning_action is None
