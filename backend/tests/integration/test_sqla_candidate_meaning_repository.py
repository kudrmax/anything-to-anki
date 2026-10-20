from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import dump_phrase
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.phrase_support import phrase
from tests.word_support import insert_word, phrase_id_of

CTX = dump_phrase(phrase("ctx"))


@pytest.mark.integration
class TestSqlaCandidateMeaningRepository:
    def setup_method(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)
        with self._Session() as s:
            insert_word(s, 1, lemma="x", phrase_text="ctx")
            s.commit()

    def test_get_returns_none_when_no_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s, SessionChangeRecorder(s))
            assert repo.get_by_phrase_id(phrase_id_of(1)) is None

    def test_upsert_inserts_new_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s, SessionChangeRecorder(s))
            entity = CandidateMeaning(
                candidate_id=1,
                meaning="hello",
                translation=None,
                synonyms=None,
                examples=None,
                ipa="həˈloʊ",
                generated_at=datetime(2026, 4, 7, tzinfo=UTC),
            )
            repo.upsert_for_phrase(phrase_id_of(1), entity)
            s.commit()

            loaded = repo.get_by_phrase_id(phrase_id_of(1))
            assert loaded is not None
            assert loaded.meaning == "hello"
            assert loaded.ipa == "həˈloʊ"

    def test_upsert_updates_existing_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s, SessionChangeRecorder(s))
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMeaning(
                candidate_id=1, meaning="v1", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMeaning(
                candidate_id=1, meaning="v2", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()

            loaded = repo.get_by_phrase_id(phrase_id_of(1))
            assert loaded is not None
            assert loaded.meaning == "v2"

    def test_get_by_phrase_ids_returns_mapping(self) -> None:
        with self._Session() as s:
            insert_word(s, 2, lemma="y", phrase_text="ctx")
            s.commit()
            repo = SqlaCandidateMeaningRepository(s, SessionChangeRecorder(s))
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMeaning(
                candidate_id=1, meaning="m1", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            repo.upsert_for_phrase(phrase_id_of(2), CandidateMeaning(
                candidate_id=2, meaning="m2", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()

            mapping = repo.get_by_phrase_ids([phrase_id_of(1), phrase_id_of(2)])
            assert set(mapping.keys()) == {phrase_id_of(1), phrase_id_of(2)}
            assert mapping[phrase_id_of(1)].meaning == "m1"

    def test_get_by_phrase_ids_empty_list(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s, SessionChangeRecorder(s))
            assert repo.get_by_phrase_ids([]) == {}

    def test_persists_translation_and_synonyms(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s, SessionChangeRecorder(s))
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMeaning(
                candidate_id=1,
                meaning="explain in detail",
                translation="разъяснить",
                synonyms="explain, clarify",
                examples=None,
                ipa=None,
                generated_at=datetime(2026, 4, 8, tzinfo=UTC),
            ))
            s.commit()

            loaded = repo.get_by_phrase_id(phrase_id_of(1))
            assert loaded is not None
            assert loaded.translation == "разъяснить"
            assert loaded.synonyms == "explain, clarify"

    def test_upsert_updates_translation_and_synonyms(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s, SessionChangeRecorder(s))
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMeaning(
                candidate_id=1, meaning="test", translation="тест", synonyms="check",
                examples=None, ipa=None, generated_at=None,
            ))
            s.commit()
            repo.upsert_for_phrase(phrase_id_of(1), CandidateMeaning(
                candidate_id=1, meaning="test", translation="обновлено", synonyms="updated",
                examples=None, ipa=None, generated_at=None,
            ))
            s.commit()

            loaded = repo.get_by_phrase_id(phrase_id_of(1))
            assert loaded is not None
            assert loaded.translation == "обновлено"
            assert loaded.synonyms == "updated"
