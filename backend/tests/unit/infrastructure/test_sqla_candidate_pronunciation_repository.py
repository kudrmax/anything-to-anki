from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import (
    CandidatePronunciationModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.sqla_candidate_pronunciation_repository import (
    SqlaCandidatePronunciationRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.word_support import insert_word

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
        session, candidate_id, source_id=source_id, status=CandidateStatus.LEARN.value,
        zipf_frequency=4.0, is_sweet_spot=True,
    )
    session.flush()


class TestGetByCandidateId:
    def test_returns_none_for_missing(self, session: Session) -> None:
        repo = SqlaCandidatePronunciationRepository(session)
        assert repo.get_by_candidate_id(999) is None

    def test_returns_entity(self, session: Session) -> None:
        _insert_candidate(session, 1)
        now = datetime(2026, 1, 1, tzinfo=UTC)
        session.add(CandidatePronunciationModel(
            candidate_id=1,
            us_audio_path="/us.mp3",
            uk_audio_path="/uk.mp3",
            generated_at=now,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        result = repo.get_by_candidate_id(1)

        assert result is not None
        assert result.candidate_id == 1
        assert result.us_audio_path == "/us.mp3"
        assert result.uk_audio_path == "/uk.mp3"


class TestGetByCandidateIds:
    def test_empty_ids_returns_empty(self, session: Session) -> None:
        repo = SqlaCandidatePronunciationRepository(session)
        assert repo.get_by_candidate_ids([]) == {}

    def test_returns_matching_entries(self, session: Session) -> None:
        _insert_candidate(session, 1)
        _insert_candidate(session, 2)
        _insert_candidate(session, 3)
        for cid in [1, 2]:
            session.add(CandidatePronunciationModel(
                candidate_id=cid,
                us_audio_path=None,
                uk_audio_path=None,
                generated_at=None,
            ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        result = repo.get_by_candidate_ids([1, 2, 3])

        assert set(result.keys()) == {1, 2}


class TestUpsert:
    def test_creates_new(self, session: Session) -> None:
        _insert_candidate(session, 1)
        repo = SqlaCandidatePronunciationRepository(session)

        entity = CandidatePronunciation(
            candidate_id=1,
            us_audio_path="/us.mp3",
            uk_audio_path=None,
            generated_at=None,
        )
        repo.upsert(entity)

        model = session.get(CandidatePronunciationModel, 1)
        assert model is not None
        assert model.us_audio_path == "/us.mp3"
        assert model.uk_audio_path is None

    def test_updates_existing(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidatePronunciationModel(
            candidate_id=1,
            us_audio_path="/old.mp3",
            uk_audio_path=None,
            generated_at=None,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        entity = CandidatePronunciation(
            candidate_id=1,
            us_audio_path="/new.mp3",
            uk_audio_path="/uk.mp3",
            generated_at=None,
        )
        repo.upsert(entity)

        model = session.get(CandidatePronunciationModel, 1)
        assert model is not None
        assert model.us_audio_path == "/new.mp3"
        assert model.uk_audio_path == "/uk.mp3"


class TestGetEligibleCandidateIds:
    def test_excludes_candidates_with_pronunciation(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=1)
        # candidate 1 already has pronunciation
        session.add(CandidatePronunciationModel(
            candidate_id=1,
            us_audio_path=None,
            uk_audio_path=None,
            generated_at=None,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        result = repo.get_eligible_candidate_ids(source_id=1)

        assert result == [2]

    def test_excludes_wrong_source(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=2)

        repo = SqlaCandidatePronunciationRepository(session)
        result = repo.get_eligible_candidate_ids(source_id=1)

        assert result == [1]

    def test_excludes_non_active_statuses(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)
        # Change candidate status to SKIP
        cand = session.get(StoredCandidateModel, 1)
        assert cand is not None
        cand.status = CandidateStatus.SKIP.value
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        result = repo.get_eligible_candidate_ids(source_id=1)

        assert result == []


class TestRowHoldingOnlyTheIpa:
    def test_is_not_a_pronunciation_and_stays_eligible(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidatePronunciationModel(candidate_id=1, ipa="/ɡleə/"))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)

        assert repo.get_by_candidate_id(1) is None
        assert repo.get_eligible_candidate_ids(source_id=1) == [1]

    def test_keeps_the_ipa_when_recordings_arrive(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidatePronunciationModel(candidate_id=1, ipa="/ɡleə/"))
        session.flush()
        repo = SqlaCandidatePronunciationRepository(session)

        repo.upsert(CandidatePronunciation(
            candidate_id=1, us_audio_path="/us.mp3", uk_audio_path=None, generated_at=None,
        ))

        row = session.get(CandidatePronunciationModel, 1)
        assert row is not None
        assert (row.ipa, row.us_audio_path) == ("/ɡleə/", "/us.mp3")
