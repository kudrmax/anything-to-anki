"""Generation results belong to phrases: the job's phrase, at the revision it expects."""
from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.use_cases.edit_card_phrase import EditCardPhraseUseCase
from backend.application.use_cases.enqueue_phrase_polish import EnqueuePhrasePolishUseCase
from backend.application.use_cases.generate_tts import GenerateTTSUseCase
from backend.application.use_cases.polish_phrases import PhrasePolishUseCase
from backend.application.use_cases.revert_phrase_polish import RevertPhrasePolishUseCase
from backend.application.use_cases.run_generation_job import MeaningGenerationUseCase
from backend.application.use_cases.set_phrase_boundary import SetPhraseBoundaryUseCase
from backend.application.utils.generation_targets import GenerationCard, PolishTarget
from backend.application.utils.job_phrases import JobPhrases
from backend.application.utils.requested_cards import RequestedCards
from backend.application.utils.rewrite_phrase import RewritePhrase
from backend.domain.entities.job import Job
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.domain.value_objects.polished_phrase import PolishedPhrase
from backend.domain.value_objects.prompts_config import PromptsConfig
from backend.infrastructure.adapters.local_media_files import LocalMediaFiles
from backend.infrastructure.persistence.database import create_session_factory
from backend.infrastructure.persistence.models import (
    Base,
    CandidateMeaningModel,
    CandidateTTSModel,
    PhraseModel,
    dump_phrase,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_job_repository import SqlaJobRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository
from sqlalchemy import select, text, update

from tests.decision_support import Decisions
from tests.integration.conftest import insert_source
from tests.lock_support import free_lock
from tests.phrase_support import phrase
from tests.word_support import CREATED_AT, TEST_SECTION, insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

SOURCE = 1
WORD = 10
PRIMARY = phrase_id_of(WORD)
OTHER_PHRASE = PRIMARY + 1
CONFIG = PromptsConfig(
    generate_meaning_user_template="{lemma} {pos} {context}",
    generate_meaning_system="system",
    generate_topic_targets_user_template="",
    generate_topic_targets_system="",
    polish_phrase_user_template="",
    polish_phrase_system="",
)


@pytest.fixture()
def factory(tmp_path: Path) -> sessionmaker[Session]:
    session_factory = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        insert_source(session, SOURCE)
        insert_word(session, WORD, source_id=SOURCE, lemma="glare")
        session.execute(
            text(
                "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by,"
                " choice, created_at, earned_section)"
                " VALUES (:id, :word, :phrase, 'manual', 'user', 'none', :created_at,"
                " :section)"
            ),
            {
                "id": OTHER_PHRASE, "word": WORD, "created_at": CREATED_AT,
                "section": TEST_SECTION,
                "phrase": dump_phrase(phrase("She glared back at him", "glared")),
            },
        )
        session.commit()
    return session_factory


def _answer() -> list[BatchMeaningResult]:
    return [BatchMeaningResult(
        word_index=1, meaning="to look angrily", translation="t", synonyms="s",
        examples="e", ipa=None,
    )]


def _meaning_use_case(session: Session, ai_service: MagicMock) -> MeaningGenerationUseCase:
    return MeaningGenerationUseCase(
        job_phrases=_job_phrases(session),
        meaning_repo=SqlaCandidateMeaningRepository(session),
        ai_service=ai_service,
        prompts_config=CONFIG,
    )


def _job_phrases(session: Session) -> JobPhrases:
    decisions = Decisions(session)
    return JobPhrases(
        SqlaCandidateRepository(session), SqlaOccurrenceRepository(session),
        decisions.word_states, decisions.vocabulary,
    )


def _meanings(factory: sessionmaker[Session]) -> dict[int, str | None]:
    with factory() as session:
        return {
            row.phrase_id: row.meaning for row in session.scalars(select(CandidateMeaningModel))
        }


def _meanwhile(
    factory: sessionmaker[Session], change: Callable[[Session], None],
) -> MagicMock:
    """An AI whose answer comes after another connection changed the phrase."""
    ai_service = MagicMock()

    def answer(_system: str, _user: str) -> list[BatchMeaningResult]:
        with factory() as other:
            change(other)
            other.commit()
        return _answer()

    ai_service.generate_meanings_batch.side_effect = answer
    return ai_service


def _bump_revision(session: Session) -> None:
    session.execute(
        update(PhraseModel).where(PhraseModel.id == PRIMARY).values(revision=1)
    )


def _delete_phrase(session: Session) -> None:
    session.execute(text("DELETE FROM phrases WHERE id = :id"), {"id": PRIMARY})


class TestStaleJobs:
    def test_a_result_for_a_phrase_rebuilt_meanwhile_is_dropped(
        self, factory: sessionmaker[Session],
    ) -> None:
        ai_service = _meanwhile(factory, _bump_revision)

        with factory() as session:
            unanswered = _meaning_use_case(session, ai_service).execute_batch(
                [PhraseRef(PRIMARY, 0)],
            )
            session.commit()

        assert unanswered == []
        assert _meanings(factory) == {}

    def test_a_job_whose_phrase_was_deleted_finishes_without_writing(
        self, factory: sessionmaker[Session],
    ) -> None:
        ai_service = _meanwhile(factory, _delete_phrase)

        with factory() as session:
            unanswered = _meaning_use_case(session, ai_service).execute_batch(
                [PhraseRef(PRIMARY, 0)],
            )
            session.commit()

        assert unanswered == []
        assert _meanings(factory) == {}

    def test_a_job_for_an_older_revision_does_not_ask_ai(
        self, factory: sessionmaker[Session],
    ) -> None:
        with factory() as session:
            _bump_revision(session)
            session.commit()
        ai_service = MagicMock()

        with factory() as session:
            unanswered = _meaning_use_case(session, ai_service).execute_batch(
                [PhraseRef(PRIMARY, 0)],
            )

        assert unanswered == []
        ai_service.generate_meanings_batch.assert_not_called()

    def test_a_result_at_the_expected_revision_is_written(
        self, factory: sessionmaker[Session],
    ) -> None:
        ai_service = MagicMock()
        ai_service.generate_meanings_batch.return_value = _answer()

        with factory() as session:
            _meaning_use_case(session, ai_service).execute_batch([PhraseRef(PRIMARY, 0)])
            session.commit()

        assert _meanings(factory) == {PRIMARY: "to look angrily"}


PHRASE_TEXT = "He glared at me."
DOCUMENT = {
    "blocks": [{"type": "paragraph", "mode": "flow", "lines": [{"text": PHRASE_TEXT}]}],
}


def _reader() -> MagicMock:
    reader = MagicMock()
    reader.read_for.side_effect = lambda text_, _lemma: phrase(text_, "glared")
    return reader


def _polished(session: Session) -> None:
    session.execute(
        update(PhraseModel).where(PhraseModel.id == PRIMARY).values(
            polished_phrase=dump_phrase(phrase("He glared.", "glared")),
        )
    )


def _set_boundary(session: Session) -> None:
    session.execute(
        text("INSERT INTO source_documents (source_id, document) VALUES (:s, :d)"),
        {"s": SOURCE, "d": json.dumps(DOCUMENT)},
    )
    SetPhraseBoundaryUseCase(
        SqlaOccurrenceRepository(session), SqlaCandidateRepository(session),
        SqlaDocumentRepository(session), _reader(), free_lock(),
    ).execute(PRIMARY, SelectionDTO(
        start_block=0, start_line=0, start_char=0,
        end_block=0, end_line=0, end_char=len(PHRASE_TEXT),
    ))


def _edit(session: Session) -> None:
    occurrences = SqlaOccurrenceRepository(session)
    EditCardPhraseUseCase(
        occurrences, SqlaCandidateRepository(session),
        RewritePhrase(_reader(), occurrences), free_lock(),
    ).execute(PRIMARY, PHRASE_TEXT)


def _polish_lands(session: Session) -> None:
    occurrences = SqlaOccurrenceRepository(session)
    occurrence = occurrences.get(PRIMARY)
    assert occurrence is not None
    RewritePhrase(_reader(), occurrences).of_phrase(occurrence, "glare", PHRASE_TEXT)


def _revert_polish(session: Session) -> None:
    RevertPhrasePolishUseCase(
        SqlaOccurrenceRepository(session), SqlaCandidateRepository(session),
        MagicMock(), free_lock(),
    ).execute(PRIMARY, reverted=True)


def _enqueue_polish(session: Session) -> None:
    occurrences = SqlaOccurrenceRepository(session)
    candidates = SqlaCandidateRepository(session)
    EnqueuePhrasePolishUseCase(
        RequestedCards(candidates, occurrences, free_lock()), occurrences,
        SqlaSourceRepository(session), SqlaJobRepository(session),
    ).execute(PRIMARY)


def _discard_polish(session: Session) -> None:
    occurrences = SqlaOccurrenceRepository(session)
    occurrence = occurrences.get(PRIMARY)
    word = SqlaCandidateRepository(session).get_by_id(WORD)
    assert occurrence is not None and word is not None
    PolishTarget(occurrences).discard(GenerationCard(word, occurrence, in_play=True))


def _revision(factory: sessionmaker[Session]) -> int:
    with factory() as session:
        found = session.get(PhraseModel, PRIMARY)
        assert found is not None
        return found.revision


class TestTextWritesOutdateJobs:
    """A job queued before the user (or a landed polish) changed the phrase's text finishes
    without writing: its result was made for the old text."""

    @pytest.mark.parametrize(
        "write",
        [_set_boundary, _edit, _polish_lands, _revert_polish, _enqueue_polish, _discard_polish],
        ids=["boundary", "edit", "polish", "revert", "enqueue_polish", "discard_polish"],
    )
    def test_a_job_queued_before_the_write_finishes_without_writing(
        self, factory: sessionmaker[Session], write: Callable[[Session], None],
    ) -> None:
        with factory() as session:
            _polished(session)
            session.commit()
        ai_service = _meanwhile(factory, write)

        with factory() as session:
            unanswered = _meaning_use_case(session, ai_service).execute_batch(
                [PhraseRef(PRIMARY, 0)],
            )
            session.commit()

        assert unanswered == []
        assert _meanings(factory) == {}
        assert _revision(factory) == 1

    def test_a_polish_queued_by_hand_carries_the_revision_after_its_write(
        self, factory: sessionmaker[Session],
    ) -> None:
        with factory() as session:
            _polished(session)
            _enqueue_polish(session)
            session.commit()

        with factory() as session:
            [job] = SqlaJobRepository(session).get_jobs_for_phrases([PRIMARY])[PRIMARY].values()
        assert job.phrase_revision == _revision(factory) == 1


def _queue_meaning(session: Session) -> None:
    SqlaJobRepository(session).enqueue([Job.queued(
        JobType.MEANING, SOURCE, WORD, phrase_id=PRIMARY, phrase_revision=0,
    )])


def _queued(factory: sessionmaker[Session]) -> dict[str, Job]:
    with factory() as session:
        return SqlaJobRepository(session).get_jobs_for_phrases([PRIMARY]).get(PRIMARY, {})


class TestQueuedJobsFollowTheText:
    """Jobs still waiting in the queue are made for the text the phrase shows when they
    run; only a running one was made for the old text."""

    def test_a_meaning_queued_behind_a_polish_runs_on_the_polished_text(
        self, factory: sessionmaker[Session],
    ) -> None:
        with factory() as session:
            _enqueue_polish(session)
            _queue_meaning(session)
            session.commit()
        with factory() as session:
            _polish_lands(session)
            session.commit()
        meaning = _queued(factory)["meaning"]
        ai_service = MagicMock()
        ai_service.generate_meanings_batch.return_value = _answer()

        with factory() as session:
            assert meaning.phrase_revision is not None
            _meaning_use_case(session, ai_service).execute_batch(
                [PhraseRef(PRIMARY, meaning.phrase_revision)],
            )
            session.commit()

        assert _meanings(factory) == {PRIMARY: "to look angrily"}
        assert PHRASE_TEXT in ai_service.generate_meanings_batch.call_args.args[1]

    def test_a_queued_polish_does_nothing_after_a_hand_edit(
        self, factory: sessionmaker[Session],
    ) -> None:
        """The hand edit fills the polished text, so the polish has nothing left to do."""
        with factory() as session:
            _enqueue_polish(session)
            session.commit()
        with factory() as session:
            _edit(session)
            session.commit()
        ai_service = MagicMock()

        _run_queued_polish(factory, ai_service)

        ai_service.polish_phrases_batch.assert_not_called()
        assert _shown_text(factory) == PHRASE_TEXT

    def test_a_queued_polish_polishes_the_new_text_after_a_boundary_change(
        self, factory: sessionmaker[Session],
    ) -> None:
        with factory() as session:
            _enqueue_polish(session)
            session.commit()
        with factory() as session:
            _set_boundary(session)
            session.commit()
        ai_service = MagicMock()
        ai_service.polish_phrases_batch.return_value = [PolishedPhrase(1, POLISHED_TEXT)]

        _run_queued_polish(factory, ai_service)

        assert PHRASE_TEXT in ai_service.polish_phrases_batch.call_args.args[1]
        assert _shown_text(factory) == POLISHED_TEXT


POLISHED_TEXT = "He glared at me angrily."
POLISH_CONFIG = dataclasses.replace(CONFIG, polish_phrase_user_template="{phrase}")


def _run_queued_polish(factory: sessionmaker[Session], ai_service: MagicMock) -> None:
    polish = _queued(factory)["polish"]
    assert polish.phrase_revision == _revision(factory)
    with factory() as session:
        occurrences = SqlaOccurrenceRepository(session)
        PhrasePolishUseCase(
            job_phrases=_job_phrases(session),
            occurrence_repo=occurrences,
            source_repo=SqlaSourceRepository(session),
            document_repo=SqlaDocumentRepository(session),
            settings_repo=MagicMock(get=MagicMock(return_value="B1")),
            enrichment_reset=MagicMock(),
            ai_service=ai_service,
            prompts_config=POLISH_CONFIG,
            rewrite_phrase=RewritePhrase(_reader(), occurrences),
        ).execute_batch([PhraseRef(PRIMARY, polish.phrase_revision)])
        session.commit()


def _shown_text(factory: sessionmaker[Session]) -> str:
    with factory() as session:
        found = SqlaOccurrenceRepository(session).get(PRIMARY)
        assert found is not None
        return found.phrase.text


class TestJobsWriteToTheirOwnPhrase:
    """A job migrated from a merged-away card points at that card's phrase, not the
    word's primary one."""

    def test_meaning_lands_on_the_phrase_of_the_job(
        self, factory: sessionmaker[Session],
    ) -> None:
        ai_service = MagicMock()
        ai_service.generate_meanings_batch.return_value = _answer()

        with factory() as session:
            _meaning_use_case(session, ai_service).execute_batch([PhraseRef(OTHER_PHRASE, 0)])
            session.commit()

        assert _meanings(factory) == {OTHER_PHRASE: "to look angrily"}
        prompt = ai_service.generate_meanings_batch.call_args.args[1]
        assert "She glared back at him" in prompt

    def test_speech_lands_on_the_phrase_of_the_job(
        self, factory: sessionmaker[Session], tmp_path: Path,
    ) -> None:
        generator = _speaking(b"speech")

        with factory() as session:
            _tts_use_case(session, generator, tmp_path).execute_one(PhraseRef(OTHER_PHRASE, 0))
            session.commit()

        assert generator.generate_audio.call_args.args[0] == "She glared back at him"
        final = _speech_folder(tmp_path) / f"p{OTHER_PHRASE}_tts.m4a"
        with factory() as session:
            rows = list(session.scalars(select(CandidateTTSModel)))
        assert [(row.phrase_id, row.audio_path) for row in rows] == [(OTHER_PHRASE, str(final))]
        assert final.read_bytes() == b"speech"
        assert sorted(p.name for p in _speech_folder(tmp_path).iterdir()) == [final.name]


class TestStaleFiles:
    """A file made for a phrase a Rebuild changed meanwhile never replaces the phrase's file."""

    def test_stale_speech_leaves_the_file_of_the_phrase_alone(
        self, factory: sessionmaker[Session], tmp_path: Path,
    ) -> None:
        final = _speech_folder(tmp_path) / f"p{PRIMARY}_tts.m4a"
        final.parent.mkdir(parents=True)
        final.write_bytes(b"fresh")

        def speak_while_rebuilt(_text: str, path: Path, _voice: str, _speed: float) -> None:
            path.write_bytes(b"stale")
            with factory() as other:
                _bump_revision(other)
                other.commit()

        generator = MagicMock()
        generator.generate_audio.side_effect = speak_while_rebuilt

        with factory() as session:
            _tts_use_case(session, generator, tmp_path).execute_one(PhraseRef(PRIMARY, 0))
            session.commit()

        assert final.read_bytes() == b"fresh"
        assert sorted(p.name for p in final.parent.iterdir()) == [final.name]
        with factory() as session:
            assert list(session.scalars(select(CandidateTTSModel))) == []

    def test_a_failed_speech_leaves_no_file_behind(
        self, factory: sessionmaker[Session], tmp_path: Path,
    ) -> None:
        def speak_then_fail(_text: str, path: Path, _voice: str, _speed: float) -> None:
            path.write_bytes(b"half")
            raise RuntimeError("kokoro crashed")

        generator = MagicMock()
        generator.generate_audio.side_effect = speak_then_fail

        with factory() as session, pytest.raises(RuntimeError):
            _tts_use_case(session, generator, tmp_path).execute_one(PhraseRef(PRIMARY, 0))

        assert list(_speech_folder(tmp_path).iterdir()) == []


def _speech_folder(tmp_path: Path) -> Path:
    return tmp_path / "media" / str(SOURCE)


def _speaking(content: bytes) -> MagicMock:
    generator = MagicMock()
    generator.generate_audio.side_effect = (
        lambda _text, path, _voice, _speed: path.write_bytes(content)
    )
    return generator


def _tts_use_case(
    session: Session, generator: MagicMock, tmp_path: Path,
) -> GenerateTTSUseCase:
    settings = MagicMock()
    settings.get.return_value = None
    return GenerateTTSUseCase(
        job_phrases=_job_phrases(session),
        tts_repo=SqlaCandidateTTSRepository(session),
        tts_generator=generator,
        settings_repo=settings,
        media_files=LocalMediaFiles(str(tmp_path / "media")),
    )
