from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import (
    CandidateTTSModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
    session.add(StoredCandidateModel(
        id=candidate_id,
        source_id=source_id,
        lemma="test",
        pos="NOUN",
        zipf_frequency=4.0,
        is_sweet_spot=True,
        context_fragment="a test",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.LEARN.value,
    ))
    session.flush()


@pytest.mark.unit
class TestUpsert:
    def test_creates_new_record(self, session: Session) -> None:
        _insert_candidate(session, 1)
        repo = SqlaCandidateTTSRepository(session)

        entity = CandidateTTS(
            candidate_id=1,
            audio_path="/audio/1_tts.m4a",
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        repo.upsert(entity)

        model = session.get(CandidateTTSModel, 1)
        assert model is not None
        assert model.audio_path == "/audio/1_tts.m4a"
        # SQLite drops timezone info, so compare naive datetimes
        assert model.generated_at is not None
        assert model.generated_at.year == 2026
        assert model.generated_at.month == 1

    def test_updates_existing_record(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidateTTSModel(
            candidate_id=1,
            audio_path="/old.m4a",
            generated_at=datetime(2025, 1, 1, tzinfo=UTC),
        ))
        session.flush()

        repo = SqlaCandidateTTSRepository(session)
        entity = CandidateTTS(
            candidate_id=1,
            audio_path="/new.m4a",
            generated_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        repo.upsert(entity)

        model = session.get(CandidateTTSModel, 1)
        assert model is not None
        assert model.audio_path == "/new.m4a"
        assert model.generated_at is not None
        assert model.generated_at.year == 2026
        assert model.generated_at.month == 6


@pytest.mark.unit
class TestGetByCandidateId:
    def test_returns_none_for_missing(self, session: Session) -> None:
        repo = SqlaCandidateTTSRepository(session)
        assert repo.get_by_candidate_id(999) is None

    def test_returns_entity_for_existing(self, session: Session) -> None:
        _insert_candidate(session, 1)
        now = datetime(2026, 3, 15, tzinfo=UTC)
        session.add(CandidateTTSModel(
            candidate_id=1,
            audio_path="/audio/1_tts.m4a",
            generated_at=now,
        ))
        session.flush()

        repo = SqlaCandidateTTSRepository(session)
        result = repo.get_by_candidate_id(1)

        assert result is not None
        assert result.candidate_id == 1
        assert result.audio_path == "/audio/1_tts.m4a"
        # SQLite drops timezone info
        assert result.generated_at is not None
        assert result.generated_at.year == 2026
        assert result.generated_at.month == 3


@pytest.mark.unit
class TestGetByCandidateIds:
    def test_empty_ids_returns_empty(self, session: Session) -> None:
        repo = SqlaCandidateTTSRepository(session)
        assert repo.get_by_candidate_ids([]) == {}

    def test_returns_matching_entries(self, session: Session) -> None:
        _insert_candidate(session, 1)
        _insert_candidate(session, 2)
        _insert_candidate(session, 3)
        for cid in [1, 3]:
            session.add(CandidateTTSModel(
                candidate_id=cid,
                audio_path=f"/audio/{cid}_tts.m4a",
                generated_at=None,
            ))
        session.flush()

        repo = SqlaCandidateTTSRepository(session)
        result = repo.get_by_candidate_ids([1, 2, 3])

        assert set(result.keys()) == {1, 3}
        assert result[1].audio_path == "/audio/1_tts.m4a"
        assert result[3].audio_path == "/audio/3_tts.m4a"


@pytest.mark.unit
class TestGetEligibleCandidateIds:
    def test_returns_pending_and_learn_without_tts(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)  # LEARN by default
        _insert_candidate(session, 2, source_id=1)
        # Change candidate 2 to PENDING
        cand2 = session.get(StoredCandidateModel, 2)
        assert cand2 is not None
        cand2.status = CandidateStatus.PENDING.value
        session.flush()

        repo = SqlaCandidateTTSRepository(session)
        result = repo.get_eligible_candidate_ids(source_id=1)

        assert set(result) == {1, 2}

    def test_excludes_candidates_with_tts(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=1)
        # candidate 1 already has TTS
        session.add(CandidateTTSModel(
            candidate_id=1,
            audio_path="/audio.m4a",
            generated_at=None,
        ))
        session.flush()

        repo = SqlaCandidateTTSRepository(session)
        result = repo.get_eligible_candidate_ids(source_id=1)

        assert result == [2]

    def test_excludes_wrong_source(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=2)

        repo = SqlaCandidateTTSRepository(session)
        result = repo.get_eligible_candidate_ids(source_id=1)

        assert result == [1]

    def test_excludes_non_active_statuses(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)
        cand = session.get(StoredCandidateModel, 1)
        assert cand is not None
        cand.status = CandidateStatus.SKIP.value
        session.flush()

        repo = SqlaCandidateTTSRepository(session)
        result = repo.get_eligible_candidate_ids(source_id=1)

        assert result == []
