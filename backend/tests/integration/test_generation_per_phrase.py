"""Generation results belong to phrases: the job's phrase, at the revision it expects."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.generate_tts import GenerateTTSUseCase
from backend.application.use_cases.run_generation_job import MeaningGenerationUseCase
from backend.application.utils.job_phrases import JobPhrases
from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
from backend.domain.value_objects.phrase_ref import PhraseRef
from backend.domain.value_objects.prompts_config import PromptsConfig
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
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import select, text, update

from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.word_support import CREATED_AT, insert_word

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration

SOURCE = 1
WORD = 10
PRIMARY = WORD
OTHER_PHRASE = 11
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
        insert_word(session, WORD, source_id=SOURCE, status="learn", lemma="glare")
        session.execute(
            text(
                "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by,"
                " skipped, is_decision, created_at)"
                " VALUES (:id, :word, :phrase, 'manual', 'user', 0, 0, :created_at)"
            ),
            {
                "id": OTHER_PHRASE, "word": WORD, "created_at": CREATED_AT,
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
    return JobPhrases(SqlaCandidateRepository(session), SqlaOccurrenceRepository(session))


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
        generator = MagicMock()
        settings = MagicMock()
        settings.get.return_value = None

        with factory() as session:
            GenerateTTSUseCase(
                job_phrases=_job_phrases(session),
                tts_repo=SqlaCandidateTTSRepository(session),
                tts_generator=generator,
                settings_repo=settings,
                media_root=str(tmp_path / "media"),
            ).execute_one(PhraseRef(OTHER_PHRASE, 0))
            session.commit()

        assert generator.generate_audio.call_args.args[0] == "She glared back at him"
        with factory() as session:
            rows = list(session.scalars(select(CandidateTTSModel)))
        assert [(row.phrase_id, row.audio_path) for row in rows] == [
            (OTHER_PHRASE, str(tmp_path / "media" / str(SOURCE) / f"p{OTHER_PHRASE}_tts.m4a")),
        ]
