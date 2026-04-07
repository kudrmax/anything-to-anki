from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)


@pytest.mark.integration
class TestSqlaCandidateMeaningRepository:
    def setup_method(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)
        # Insert a fake candidate row so FK semantics make sense — we use raw SQL
        # because we only need the ID to satisfy the 1:1 relationship at the
        # application level (no actual FK in this phase).
        with self._Session() as s:
            s.execute(
                text(
                    "INSERT INTO candidates (id, source_id, lemma, pos, cefr_level, "
                    "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
                    "occurrences, status, is_phrasal_verb) "
                    "VALUES (1, 1, 'x', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0)"
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
                ipa="həˈloʊ",
                status=EnrichmentStatus.DONE,
                error=None,
                generated_at=datetime(2026, 4, 7, tzinfo=UTC),
            )
            repo.upsert(entity)
            s.commit()

            loaded = repo.get_by_candidate_id(1)
            assert loaded is not None
            assert loaded.meaning == "hello"
            assert loaded.ipa == "həˈloʊ"
            assert loaded.status == EnrichmentStatus.DONE

    def test_upsert_updates_existing_row(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s)
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="v1", ipa=None,
                status=EnrichmentStatus.DONE, error=None, generated_at=None,
            ))
            s.commit()
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="v2", ipa=None,
                status=EnrichmentStatus.DONE, error=None, generated_at=None,
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
                    "occurrences, status, is_phrasal_verb) "
                    "VALUES (2, 1, 'y', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0)"
                )
            )
            s.commit()
            repo = SqlaCandidateMeaningRepository(s)
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="m1", ipa=None,
                status=EnrichmentStatus.DONE, error=None, generated_at=None,
            ))
            repo.upsert(CandidateMeaning(
                candidate_id=2, meaning="m2", ipa=None,
                status=EnrichmentStatus.DONE, error=None, generated_at=None,
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
                "occurrences, status, is_phrasal_verb) "
                "VALUES (2, 1, 'y', 'NOUN', 'B2', 3.0, 0, 'ctx', 'clean', 1, 'pending', 0)"
            ))
            s.commit()
            repo = SqlaCandidateMeaningRepository(s)
            repo.upsert(CandidateMeaning(
                candidate_id=1, meaning="m1", ipa=None,
                status=EnrichmentStatus.DONE, error=None, generated_at=None,
            ))
            repo.upsert(CandidateMeaning(
                candidate_id=2, meaning="m2", ipa=None,
                status=EnrichmentStatus.DONE, error=None, generated_at=None,
            ))
            s.commit()

            mapping = repo.get_by_candidate_ids([1, 2])
            assert set(mapping.keys()) == {1, 2}
            assert mapping[1].meaning == "m1"

    def test_get_by_candidate_ids_empty_list(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateMeaningRepository(s)
            assert repo.get_by_candidate_ids([]) == {}
