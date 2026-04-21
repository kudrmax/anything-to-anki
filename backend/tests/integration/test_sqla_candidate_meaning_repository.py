from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.mark.integration
class TestSqlaCandidateMeaningRepository:
    def setup_method(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)
        with self._Session() as s:
            s.execute(
                text(
                    "INSERT INTO candidates (id, source_id, lemma, pos, cefr_level, "
                    "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
                    "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
                    "VALUES (1, 1, 'x', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0, 0)"
                )
            )
            s.commit()

    def test_get_returns_none_when_no_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s)
            assert repo.get_by_candidate_id(1) is None

    def test_upsert_inserts_new_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s)
            entity = CandidateMeaning(
                candidate_id=1,
                meaning="hello",
                translation=None,
                synonyms=None,
                examples=None,
                ipa="həˈloʊ",
                generated_at=datetime(2026, 4, 7, tzinfo=UTC),
            )
            repo.upsert(entity)
            s.commit()

            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.meaning == "hello"
            assert loaded.ipa == "həˈloʊ"

    def test_upsert_updates_existing_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s)
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="v1", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="v2", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()

            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.meaning == "v2"

    def test_get_all_by_source_returns_mapping(self) -> None:
        with self._Session() as s:
            # add another candidate
            s.execute(
                text(
                    "INSERT INTO candidates (id, source_id, lemma, pos, cefr_level, "
                    "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
                    "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
                    "VALUES (2, 1, 'y', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0, 0)"
                )
            )
            s.commit()
            repo = SqlaCandidateMeaningRepository(s)
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="m1", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            repo.upsert(CandidateMeaning(
                candidate_id=2, meaning="m2", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()

            mapping = repo.get_all_by_source(source_id=1)
            assert set(mapping.keys()) == {1, 2}
            assert mapping[1].meaning == "m1"
            assert mapping[2].meaning == "m2"

    def test_get_by_candidate_ids_returns_mapping(self) -> None:
        with self._Session() as s:
            s.execute(text(
                "INSERT INTO candidates (id, source_id, lemma, pos, cefr_level, "
                "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
                "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
                "VALUES (2, 1, 'y', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0, 0)"
            ))
            s.commit()
            repo = SqlaCandidateMeaningRepository(s)
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="m1", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            repo.upsert(CandidateMeaning(
                candidate_id=2, meaning="m2", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()

            mapping = repo.get_by_candidate_ids([1, 2])
            assert set(mapping.keys()) == {1, 2}
            assert mapping[1].meaning == "m1"

    def test_get_by_candidate_ids_empty_list(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s)
            assert repo.get_by_candidate_ids([]) == {}

    def test_get_candidate_ids_without_meaning_returns_only_missing(self) -> None:
        with self._Session() as s:
            s.execute(text(
                "INSERT INTO candidates (id, source_id, lemma, pos, cefr_level, "
                "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
                "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
                "VALUES (2, 1, 'y', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0, 0)"
            ))
            s.commit()
            repo = SqlaCandidateMeaningRepository(s)
            # candidate 1 has meaning, candidate 2 does not
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="x", translation=None, synonyms=None, examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()

            ids = repo.get_candidate_ids_without_meaning(source_id=1, only_active=True)
            assert ids == [2]

    def test_count_candidate_ids_without_meaning(self) -> None:
        with self._Session() as s:
            s.execute(text(
                "INSERT INTO candidates (id, source_id, lemma, pos, cefr_level, "
                "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
                "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
                "VALUES (2, 1, 'y', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'known', 0, 0)"
            ))
            s.commit()
            repo = SqlaCandidateMeaningRepository(s)
            # 2 candidates, neither has meaning, but only 1 active (PENDING)
            assert repo.count_candidate_ids_without_meaning(source_id=1, only_active=True) == 1
            assert repo.count_candidate_ids_without_meaning(source_id=1, only_active=False) == 2

    def test_persists_translation_and_synonyms(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s)
            repo.upsert(CandidateMeaning(
                candidate_id=1,
                meaning="explain in detail",
                translation="разъяснить",
                synonyms="explain, clarify",
                examples=None,
                ipa=None,
                generated_at=datetime(2026, 4, 8, tzinfo=UTC),
            ))
            s.commit()

            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.translation == "разъяснить"
            assert loaded.synonyms == "explain, clarify"

    def test_upsert_updates_translation_and_synonyms(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s)
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="test", translation="тест", synonyms="check", examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="test", translation="обновлено", synonyms="updated", examples=None,
                ipa=None, generated_at=None,
            ))
            s.commit()

            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.translation == "обновлено"
            assert loaded.synonyms == "updated"
