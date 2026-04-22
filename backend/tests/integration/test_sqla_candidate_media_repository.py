from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_media import CandidateMedia
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _insert_candidate(session: Session, cid: int) -> None:
    session.execute(text(
        "INSERT INTO candidates (id, source_id, lemma, pos, "
        "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
        "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
        f"VALUES ({cid}, 1, 'x', 'NOUN', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0, 0)"
    ))


@pytest.mark.integration
class TestSqlaCandidateMediaRepository:
    def setup_method(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)
        with self._Session() as s:
            _insert_candidate(s, 1)
            s.commit()

    def test_get_returns_none_when_no_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            assert repo.get_by_candidate_id(1) is None

    def test_upsert_inserts_new_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            entity = CandidateMedia(
                candidate_id=1,
                screenshot_path="/m/1.webp",
                audio_path="/m/1.m4a",
                start_ms=100,
                end_ms=200,
                status=EnrichmentStatus.DONE,
                error=None,
                generated_at=None,
            )
            repo.upsert(entity)
            s.commit()

            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.screenshot_path == "/m/1.webp"
            assert loaded.start_ms == 100

    def test_upsert_updates_existing_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path="/old.webp", audio_path=None,
                start_ms=0, end_ms=10, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            s.commit()
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path="/new.webp", audio_path=None,
                start_ms=0, end_ms=10, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            s.commit()
            assert repo.get_by_candidate_id(1).screenshot_path == "/new.webp"

    def test_clear_paths_only_screenshot(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1,
                screenshot_path="/s.webp",
                audio_path="/a.m4a",
                start_ms=0, end_ms=10,
                status=EnrichmentStatus.DONE, error=None, generated_at=None,
            ))
            s.commit()

            repo.clear_paths(1, clear_screenshot=True, clear_audio=False)
            s.commit()

            loaded = repo.get_by_candidate_id(1)
            assert loaded.screenshot_path is None
            assert loaded.audio_path == "/a.m4a"

    def test_clear_paths_no_op_when_no_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            # Should not raise
            repo.clear_paths(1, clear_screenshot=True, clear_audio=True)
            s.commit()

    def test_get_all_by_source(self) -> None:
        with self._Session() as s:
            _insert_candidate(s, 2)
            s.commit()
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path="/1.webp", audio_path=None,
                start_ms=0, end_ms=10, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            repo.upsert(CandidateMedia(
                candidate_id=2, screenshot_path="/2.webp", audio_path=None,
                start_ms=0, end_ms=10, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            s.commit()

            mapping = repo.get_all_by_source(source_id=1)
            assert set(mapping.keys()) == {1, 2}

    def test_get_by_candidate_ids_returns_mapping(self) -> None:
        with self._Session() as s:
            _insert_candidate(s, 2)
            s.commit()
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path="/1.webp", audio_path=None,
                start_ms=0, end_ms=10, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            repo.upsert(CandidateMedia(
                candidate_id=2, screenshot_path="/2.webp", audio_path=None,
                start_ms=0, end_ms=10, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            s.commit()

            mapping = repo.get_by_candidate_ids([1, 2])
            assert set(mapping.keys()) == {1, 2}
            assert mapping[1].screenshot_path == "/1.webp"

    def test_get_by_candidate_ids_empty_list(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            assert repo.get_by_candidate_ids([]) == {}

    def test_get_eligible_candidate_ids(self) -> None:
        with self._Session() as s:
            _insert_candidate(s, 2)
            _insert_candidate(s, 3)
            # candidate 1: has timecodes, no screenshot → eligible
            # candidate 2: has timecodes AND screenshot → NOT eligible
            # candidate 3: no media row → NOT eligible
            s.commit()
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path=None, audio_path=None,
                start_ms=10, end_ms=20, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            repo.upsert(CandidateMedia(
                candidate_id=2, screenshot_path="/x.webp", audio_path=None,
                start_ms=10, end_ms=20, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            s.commit()

            ids = repo.get_eligible_candidate_ids(source_id=1)
            assert ids == [1]

    def test_get_eligible_candidate_ids_excludes_non_active_status(self) -> None:
        with self._Session() as s:
            # Insert candidate with status='known' (not active)
            s.execute(text(
                "INSERT INTO candidates (id, source_id, lemma, pos, "
                "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
                "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
                "VALUES (4, 1, 'z', 'NOUN', 3.0, 0, 'ctx', 'clean', 1, 'known', 0, 0)"
            ))
            s.commit()
            repo = SqlaCandidateMediaRepository(s)
            # candidate 4 has timecodes and no screenshot, but status=known → NOT eligible
            repo.upsert(CandidateMedia(
                candidate_id=4, screenshot_path=None, audio_path=None,
                start_ms=10, end_ms=20, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            s.commit()

            ids = repo.get_eligible_candidate_ids(source_id=1)
            assert 4 not in ids

    def test_mark_queued_bulk_preserves_timecodes(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path="/old.webp", audio_path="/old.m4a",
                start_ms=100, end_ms=200,
                status=EnrichmentStatus.DONE, error=None, generated_at=None,
            ))
            s.commit()
            repo.mark_queued_bulk([1])
            s.commit()
            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.status == EnrichmentStatus.QUEUED
            # Timecodes and paths preserved
            assert loaded.start_ms == 100
            assert loaded.end_ms == 200
            assert loaded.screenshot_path == "/old.webp"

    def test_mark_queued_bulk_creates_new_row(self) -> None:
        with self._Session() as s:
            _insert_candidate(s, 2)
            s.commit()
            repo = SqlaCandidateMediaRepository(s)
            # candidate 2: no existing row
            repo.mark_queued_bulk([2])
            s.commit()
            loaded = repo.get_by_candidate_id(2)
            assert loaded is not None
            assert loaded.status == EnrichmentStatus.QUEUED
            assert loaded.start_ms is None
            assert loaded.screenshot_path is None

    def test_mark_running_flips_status(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path=None, audio_path=None,
                start_ms=None, end_ms=None,
                status=EnrichmentStatus.QUEUED, error=None, generated_at=None,
            ))
            s.commit()
            repo.mark_running(1)
            s.commit()
            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.status == EnrichmentStatus.RUNNING

    def test_mark_failed_sets_error(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path=None, audio_path=None,
                start_ms=None, end_ms=None,
                status=EnrichmentStatus.RUNNING, error=None, generated_at=None,
            ))
            s.commit()
            repo.mark_failed(1, "ffmpeg died")
            s.commit()
            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.status == EnrichmentStatus.FAILED
            assert loaded.error == "ffmpeg died"

    def test_mark_batch_failed(self) -> None:
        with self._Session() as s:
            _insert_candidate(s, 2)
            s.commit()
            repo = SqlaCandidateMediaRepository(s)
            repo.mark_queued_bulk([1, 2])
            s.commit()
            repo.mark_batch_failed([1, 2], "disk full")
            s.commit()
            r1 = repo.get_by_candidate_id(1)
            r2 = repo.get_by_candidate_id(2)
            assert r1 is not None and r1.status == EnrichmentStatus.FAILED
            assert r2 is not None and r2.status == EnrichmentStatus.FAILED
            assert r1.error == "disk full"

    def test_get_candidate_ids_by_status_failed(self) -> None:
        with self._Session() as s:
            _insert_candidate(s, 2)
            s.commit()
            repo = SqlaCandidateMediaRepository(s)
            repo.upsert(CandidateMedia(
                candidate_id=1, screenshot_path="/1.webp", audio_path=None,
                start_ms=0, end_ms=10, status=EnrichmentStatus.DONE,
                error=None, generated_at=None,
            ))
            repo.upsert(CandidateMedia(
                candidate_id=2, screenshot_path=None, audio_path=None,
                start_ms=None, end_ms=None,
                status=EnrichmentStatus.FAILED, error="boom", generated_at=None,
            ))
            s.commit()
            failed_ids = repo.get_candidate_ids_by_status(1, EnrichmentStatus.FAILED)
            assert failed_ids == [2]
