from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.value_objects.document_position import DocumentPosition
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import dump_phrase
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tests.phrase_support import phrase

_NOW = datetime(2026, 10, 4, tzinfo=UTC)
SOURCE_TEXT = "The air was stale"


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
                    "zipf_frequency, is_sweet_spot, source_phrase, "
                    "occurrences, status, is_phrasal_verb) "
                    "VALUES (1, 1, 'stale', 'ADJ', 3.0, 0, :phrase, "
                    "1, 'pending', 0)"
                ),
                {"phrase": dump_phrase(phrase(SOURCE_TEXT, "stale"))},
            )
            s.commit()

    def test_new_candidate_is_not_polished(self) -> None:
        with self._Session() as s:
            candidate = SqlaCandidateRepository(s).get_by_id(1)
            assert candidate is not None
            assert candidate.polished_phrase is None
            assert not candidate.polish_reverted

    def test_polish_and_revert_round_trip(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateRepository(s)
            repo.set_polished_phrase(1, phrase("The air was not fresh, stale.", "stale"))
            repo.set_polish_reverted(1, True)
            s.commit()
        with self._Session() as s:
            candidate = SqlaCandidateRepository(s).get_by_id(1)
            assert candidate is not None
            assert candidate.polished_phrase == phrase("The air was not fresh, stale.", "stale")
            assert candidate.polish_reverted
            assert candidate.phrase.text == SOURCE_TEXT

    def test_new_polish_clears_revert(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateRepository(s)
            repo.set_polished_phrase(1, phrase("Old stale air.", "stale"))
            repo.set_polish_reverted(1, True)
            repo.set_polished_phrase(1, phrase("The stale air.", "stale"))
            s.commit()
            candidate = repo.get_by_id(1)
            assert candidate is not None
            assert not candidate.polish_reverted

    def test_new_source_phrase_drops_polish(self) -> None:
        with self._Session() as s:
            repo = SqlaCandidateRepository(s)
            repo.set_polished_phrase(1, phrase("The stale air.", "stale"))
            repo.set_polish_reverted(1, True)
            new_phrase = phrase("The air around us was stale", "stale")
            repo.set_source_phrase(1, new_phrase, DocumentPosition(0, 0, 0, 0, 27))
            s.commit()
            candidate = repo.get_by_id(1)
            assert candidate is not None
            assert candidate.source_phrase == new_phrase
            assert candidate.polished_phrase is None
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
