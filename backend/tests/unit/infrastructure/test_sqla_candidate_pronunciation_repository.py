from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
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
            status=EnrichmentStatus.DONE.value,
            error=None,
            generated_at=now,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        result = repo.get_by_candidate_id(1)

        assert result is not None
        assert result.candidate_id == 1
        assert result.us_audio_path == "/us.mp3"
        assert result.uk_audio_path == "/uk.mp3"
        assert result.status == EnrichmentStatus.DONE


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
                status=EnrichmentStatus.DONE.value,
                error=None,
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
            status=EnrichmentStatus.DONE,
            error=None,
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
            status=EnrichmentStatus.QUEUED.value,
            error=None,
            generated_at=None,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        entity = CandidatePronunciation(
            candidate_id=1,
            us_audio_path="/new.mp3",
            uk_audio_path="/uk.mp3",
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=None,
        )
        repo.upsert(entity)

        model = session.get(CandidatePronunciationModel, 1)
        assert model is not None
        assert model.us_audio_path == "/new.mp3"
        assert model.uk_audio_path == "/uk.mp3"
        assert model.status == EnrichmentStatus.DONE.value


class TestMarkQueuedBulk:
    def test_empty_ids_is_noop(self, session: Session) -> None:
        repo = SqlaCandidatePronunciationRepository(session)
        repo.mark_queued_bulk([])  # should not raise

    def test_creates_new_rows(self, session: Session) -> None:
        _insert_candidate(session, 1)
        _insert_candidate(session, 2)
        repo = SqlaCandidatePronunciationRepository(session)

        repo.mark_queued_bulk([1, 2])

        for cid in [1, 2]:
            model = session.get(CandidatePronunciationModel, cid)
            assert model is not None
            assert model.status == EnrichmentStatus.QUEUED.value

    def test_updates_existing_rows(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidatePronunciationModel(
            candidate_id=1,
            us_audio_path="/us.mp3",
            uk_audio_path=None,
            status=EnrichmentStatus.FAILED.value,
            error="some error",
            generated_at=None,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        repo.mark_queued_bulk([1])

        model = session.get(CandidatePronunciationModel, 1)
        assert model is not None
        assert model.status == EnrichmentStatus.QUEUED.value
        assert model.error is None


class TestMarkRunning:
    def test_transitions_queued_to_running(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidatePronunciationModel(
            candidate_id=1,
            us_audio_path=None,
            uk_audio_path=None,
            status=EnrichmentStatus.QUEUED.value,
            error=None,
            generated_at=None,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        repo.mark_running(1)

        model = session.get(CandidatePronunciationModel, 1)
        assert model is not None
        assert model.status == EnrichmentStatus.RUNNING.value

    def test_does_not_transition_done(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidatePronunciationModel(
            candidate_id=1,
            us_audio_path=None,
            uk_audio_path=None,
            status=EnrichmentStatus.DONE.value,
            error=None,
            generated_at=None,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        repo.mark_running(1)

        model = session.get(CandidatePronunciationModel, 1)
        assert model is not None
        assert model.status == EnrichmentStatus.DONE.value


class TestMarkFailed:
    def test_sets_failed_status_and_error(self, session: Session) -> None:
        _insert_candidate(session, 1)
        session.add(CandidatePronunciationModel(
            candidate_id=1,
            us_audio_path=None,
            uk_audio_path=None,
            status=EnrichmentStatus.RUNNING.value,
            error=None,
            generated_at=None,
        ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        repo.mark_failed(1, "download failed")

        model = session.get(CandidatePronunciationModel, 1)
        assert model is not None
        assert model.status == EnrichmentStatus.FAILED.value
        assert model.error == "download failed"


class TestMarkBatchCancelled:
    def test_empty_ids_is_noop(self, session: Session) -> None:
        repo = SqlaCandidatePronunciationRepository(session)
        repo.mark_batch_cancelled([])  # should not raise

    def test_cancels_multiple(self, session: Session) -> None:
        for cid in [1, 2]:
            _insert_candidate(session, cid)
            session.add(CandidatePronunciationModel(
                candidate_id=cid,
                us_audio_path=None,
                uk_audio_path=None,
                status=EnrichmentStatus.QUEUED.value,
                error=None,
                generated_at=None,
            ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        repo.mark_batch_cancelled([1, 2])

        for cid in [1, 2]:
            model = session.get(CandidatePronunciationModel, cid)
            assert model is not None
            assert model.status == EnrichmentStatus.CANCELLED.value
            assert model.error == "cancelled by user"


class TestFailAllRunning:
    def test_returns_zero_when_none_running(self, session: Session) -> None:
        repo = SqlaCandidatePronunciationRepository(session)
        assert repo.fail_all_running("crash") == 0

    def test_fails_running_rows(self, session: Session) -> None:
        for cid in [1, 2, 3]:
            _insert_candidate(session, cid)
        statuses = [
            (1, EnrichmentStatus.RUNNING),
            (2, EnrichmentStatus.RUNNING),
            (3, EnrichmentStatus.DONE),
        ]
        for cid, status in statuses:
            session.add(CandidatePronunciationModel(
                candidate_id=cid,
                us_audio_path=None,
                uk_audio_path=None,
                status=status.value,
                error=None,
                generated_at=None,
            ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        count = repo.fail_all_running("worker crash")

        assert count == 2
        for cid in [1, 2]:
            model = session.get(CandidatePronunciationModel, cid)
            assert model is not None
            assert model.status == EnrichmentStatus.FAILED.value
            assert model.error == "worker crash"
        # cid=3 should remain DONE
        model3 = session.get(CandidatePronunciationModel, 3)
        assert model3 is not None
        assert model3.status == EnrichmentStatus.DONE.value


class TestGetEligibleCandidateIds:
    def test_excludes_candidates_with_pronunciation(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=1)
        # candidate 1 already has pronunciation
        session.add(CandidatePronunciationModel(
            candidate_id=1,
            us_audio_path=None,
            uk_audio_path=None,
            status=EnrichmentStatus.DONE.value,
            error=None,
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


class TestGetCandidateIdsByStatus:
    def test_returns_matching(self, session: Session) -> None:
        for cid in [1, 2, 3]:
            _insert_candidate(session, cid, source_id=1)
        statuses = [
            (1, EnrichmentStatus.QUEUED),
            (2, EnrichmentStatus.DONE),
            (3, EnrichmentStatus.QUEUED),
        ]
        for cid, status in statuses:
            session.add(CandidatePronunciationModel(
                candidate_id=cid,
                us_audio_path=None,
                uk_audio_path=None,
                status=status.value,
                error=None,
                generated_at=None,
            ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        result = repo.get_candidate_ids_by_status(source_id=1, status=EnrichmentStatus.QUEUED)

        assert sorted(result) == [1, 3]

    def test_filters_by_source(self, session: Session) -> None:
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=2)
        for cid in [1, 2]:
            session.add(CandidatePronunciationModel(
                candidate_id=cid,
                us_audio_path=None,
                uk_audio_path=None,
                status=EnrichmentStatus.QUEUED.value,
                error=None,
                generated_at=None,
            ))
        session.flush()

        repo = SqlaCandidatePronunciationRepository(session)
        result = repo.get_candidate_ids_by_status(source_id=1, status=EnrichmentStatus.QUEUED)

        assert result == [1]
