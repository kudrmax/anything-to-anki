from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import (
    CandidateTTSModel,
)
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    yield s
    s.close()


def _insert_candidate(session: Session, candidate_id: int, source_id: int = 1) -> None:
    insert_word(
        session, candidate_id, source_id=source_id, status="learn",
        zipf_frequency=4.0, is_sweet_spot=True,
    )
    session.flush()


@pytest.mark.unit
class TestUpsert:
    def test_creates_new_record(self, session: Session) -> None:
        _insert_candidate(session, 1)
        repo = SqlaCandidateTTSRepository(session, SessionChangeRecorder(session))

        entity = CandidateTTS(
            candidate_id=1,
            audio_path="/audio/1_tts.m4a",
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        repo.upsert_for_phrase(phrase_id_of(1), entity)

        model = session.get(CandidateTTSModel, phrase_id_of(1))
        assert model is not None
        assert model.audio_path == "/audio/1_tts.m4a"
        # SQLite drops timezone info, so compare naive datetimes
        assert model.generated_at is not None
        assert model.generated_at.year == 2026
        assert model.generated_at.month == 1

    def test_updates_existing_record(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidateTTSModel(
            phrase_id=phrase_id_of(1),
            audio_path="/old.m4a",
            generated_at=datetime(2025, 1, 1, tzinfo=UTC),
        ))
        session.flush()

        repo = SqlaCandidateTTSRepository(session, SessionChangeRecorder(session))
        entity = CandidateTTS(
            candidate_id=1,
            audio_path="/new.m4a",
            generated_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        repo.upsert_for_phrase(phrase_id_of(1), entity)

        model = session.get(CandidateTTSModel, phrase_id_of(1))
        assert model is not None
        assert model.audio_path == "/new.m4a"
        assert model.generated_at is not None
        assert model.generated_at.year == 2026
        assert model.generated_at.month == 6


@pytest.mark.unit
class TestGetByPhraseId:
    def test_returns_none_for_missing(self, session: Session) -> None:
        repo = SqlaCandidateTTSRepository(session, SessionChangeRecorder(session))
        assert repo.get_by_phrase_id(phrase_id_of(999)) is None

    def test_returns_entity_for_existing(self, session: Session) -> None:
        _insert_candidate(session, 1)
        now = datetime(2026, 3, 15, tzinfo=UTC)
        session.add(CandidateTTSModel(
            phrase_id=phrase_id_of(1),
            audio_path="/audio/1_tts.m4a",
            generated_at=now,
        ))
        session.flush()

        repo = SqlaCandidateTTSRepository(session, SessionChangeRecorder(session))
        result = repo.get_by_phrase_id(phrase_id_of(1))

        assert result is not None
        assert result.candidate_id == 1
        assert result.audio_path == "/audio/1_tts.m4a"
        # SQLite drops timezone info
        assert result.generated_at is not None
        assert result.generated_at.year == 2026
        assert result.generated_at.month == 3


@pytest.mark.unit
class TestGetByPhraseIds:
    def test_empty_ids_returns_empty(self, session: Session) -> None:
        repo = SqlaCandidateTTSRepository(session, SessionChangeRecorder(session))
        assert repo.get_by_phrase_ids([]) == {}

    def test_returns_matching_entries(self, session: Session) -> None:
        _insert_candidate(session, 1)
        _insert_candidate(session, 2)
        _insert_candidate(session, 3)
        for cid in [1, 3]:
            session.add(CandidateTTSModel(
                phrase_id=phrase_id_of(cid),
                audio_path=f"/audio/{cid}_tts.m4a",
                generated_at=None,
            ))
        session.flush()

        repo = SqlaCandidateTTSRepository(session, SessionChangeRecorder(session))
        result = repo.get_by_phrase_ids([phrase_id_of(1), phrase_id_of(2), phrase_id_of(3)])

        assert set(result.keys()) == {phrase_id_of(1), phrase_id_of(3)}
        assert result[phrase_id_of(1)].audio_path == "/audio/1_tts.m4a"
        assert result[phrase_id_of(3)].audio_path == "/audio/3_tts.m4a"
