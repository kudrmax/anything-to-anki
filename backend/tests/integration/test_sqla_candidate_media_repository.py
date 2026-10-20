from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_media import CandidateMedia
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import dump_phrase
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.phrase_support import phrase
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

CTX = dump_phrase(phrase("ctx"))


def _insert_candidate(session: Session, cid: int) -> None:
    insert_word(session, cid, phrase_text="ctx")


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
            repo = SqlaCandidateMediaRepository(s, SessionChangeRecorder(s))
            assert repo.get_by_phrase_id(phrase_id_of(1)) is None

    def test_upsert_inserts_new_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s, SessionChangeRecorder(s))
            entity = CandidateMedia(
                candidate_id=1,
                screenshot_path="/m/1.webp",
                audio_path="/m/1.m4a",
                start_ms=100,
                end_ms=200,
                generated_at=None,
            )
            repo.upsert_for_phrase(phrase_id_of(1), entity)
            s.commit()

            loaded = repo.get_by_phrase_id(phrase_id_of(1))
            assert loaded is not None
            assert loaded.screenshot_path == "/m/1.webp"
            assert loaded.start_ms == 100

    def test_upsert_updates_existing_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s, SessionChangeRecorder(s))
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMedia(
                candidate_id=1, screenshot_path="/old.webp", audio_path=None,
                start_ms=0, end_ms=10, generated_at=None,
            ))
            s.commit()
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMedia(
                candidate_id=1, screenshot_path="/new.webp", audio_path=None,
                start_ms=0, end_ms=10, generated_at=None,
            ))
            s.commit()
            loaded = repo.get_by_phrase_id(phrase_id_of(1))
            assert loaded is not None
            assert loaded.screenshot_path == "/new.webp"

    def test_clear_paths_only_screenshot(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s, SessionChangeRecorder(s))
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMedia(
                candidate_id=1,
                screenshot_path="/s.webp",
                audio_path="/a.m4a",
                start_ms=0, end_ms=10,
                generated_at=None,
            ))
            s.commit()

            repo.clear_phrase_paths(phrase_id_of(1), clear_screenshot=True, clear_audio=False)
            s.commit()

            loaded = repo.get_by_phrase_id(phrase_id_of(1))
            assert loaded is not None
            assert loaded.screenshot_path is None
            assert loaded.audio_path == "/a.m4a"

    def test_clear_paths_no_op_when_no_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s, SessionChangeRecorder(s))
            # Should not raise
            repo.clear_phrase_paths(phrase_id_of(1), clear_screenshot=True, clear_audio=True)
            s.commit()

    def test_get_by_phrase_ids_returns_mapping(self) -> None:
        with self._Session() as s:
            _insert_candidate(s, 2)
            s.commit()
            repo = SqlaCandidateMediaRepository(s, SessionChangeRecorder(s))
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMedia(
                candidate_id=1, screenshot_path="/1.webp", audio_path=None,
                start_ms=0, end_ms=10, generated_at=None,
            ))
            repo.upsert_for_phrase(phrase_id_of(2), CandidateMedia(
                candidate_id=2, screenshot_path="/2.webp", audio_path=None,
                start_ms=0, end_ms=10, generated_at=None,
            ))
            s.commit()

            mapping = repo.get_by_phrase_ids([phrase_id_of(1), phrase_id_of(2)])
            assert set(mapping.keys()) == {phrase_id_of(1), phrase_id_of(2)}
            assert mapping[phrase_id_of(1)].screenshot_path == "/1.webp"

    def test_get_by_phrase_ids_empty_list(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMediaRepository(s, SessionChangeRecorder(s))
            assert repo.get_by_phrase_ids([]) == {}
