from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_NOW = datetime(2026, 10, 4, tzinfo=UTC)


@pytest.mark.integration
class TestCandidatePolishPersistence:
    def setup_method(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)
        with self._Session() as s:
            s.execute(
                text(
                    "INSERT INTO candidates (id, source_id, lemma, pos, "
                    "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
                    "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
                    "VALUES (1, 1, 'stale', 'ADJ', 3.0, 0, 'The air was stale', 'clean', "
                    "1, 'pending', 0, 0)"
                )
            )
            s.commit()

    def test_new_candidate_is_not_polished(self) -> None:
        with self._Session() as s:
            candidate = SqlaCandidateRepository(s).get_by_id(1)
            assert candidate is not None
            assert candidate.polished_fragment is None
            assert not candidate.polish_reverted

    def test_polish_and_revert_round_trip(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateRepository(s)
            repo.set_polished_fragment(1, "The air was not fresh, stale.")
            repo.set_polish_reverted(1, True)
            s.commit()
        with self._Session() as s:
            candidate = SqlaCandidateRepository(s).get_by_id(1)
            assert candidate is not None
            assert candidate.polished_fragment == "The air was not fresh, stale."
            assert candidate.polish_reverted
            assert candidate.card_phrase == "The air was stale"

    def test_new_polish_clears_revert(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateRepository(s)
            repo.set_polished_fragment(1, "Old stale air.")
            repo.set_polish_reverted(1, True)
            repo.set_polished_fragment(1, "The stale air.")
            s.commit()
            candidate = repo.get_by_id(1)
            assert candidate is not None
            assert not candidate.polish_reverted

    def test_new_source_phrase_drops_polish(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateRepository(s)
            repo.set_polished_fragment(1, "The stale air.")
            repo.set_polish_reverted(1, True)
            repo.update_context_fragment(1, "The air around us was stale")
            s.commit()
            candidate = repo.get_by_id(1)
            assert candidate is not None
            assert candidate.polished_fragment is None
            assert not candidate.polish_reverted

    def test_meaning_and_tts_can_be_dropped(self) -> None:
        with self._Session() as s:
            meanings = SqlaCandidateMeaningRepository(s)
            tts = SqlaCandidateTTSRepository(s)
            meanings.upsert(CandidateMeaning(
                candidate_id=1, meaning="m", translation=None, synonyms=None,
                examples=None, ipa=None, generated_at=_NOW,
            ))
            tts.upsert(CandidateTTS(candidate_id=1, audio_path="a.m4a", generated_at=_NOW))
            meanings.delete_by_candidate_id(1)
            tts.delete_by_candidate_id(1)
            s.commit()
            assert meanings.get_by_candidate_id(1) is None
            assert tts.get_by_candidate_id(1) is None
