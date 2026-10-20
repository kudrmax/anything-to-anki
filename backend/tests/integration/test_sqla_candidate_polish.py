from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.candidate_tts import CandidateTTS
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.document_position import DocumentPosition
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_tts_repository import (
    SqlaCandidateTTSRepository,
)
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.phrase_support import phrase
from tests.word_support import insert_word, phrase_id_of

_NOW = datetime(2026, 10, 4, tzinfo=UTC)
SOURCE_TEXT = "The air was stale"
PHRASE_ID = phrase_id_of(1)


@pytest.mark.integration
class TestPhrasePolishPersistence:
    def setup_method(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)
        with self._Session() as s:
            insert_word(s, 1, lemma="stale", pos="ADJ", phrase_text=SOURCE_TEXT)
            s.commit()

    def test_new_phrase_is_not_polished(self) -> None:
        with self._Session() as s:
            occ = SqlaOccurrenceRepository(s).get(PHRASE_ID)
            assert occ is not None
            assert occ.polished_phrase is None
            assert not occ.polish_reverted

    def test_polish_and_revert_round_trip(self) -> None:
        polished = phrase("The air was not fresh, stale.", "stale")
        with self._Session() as s:
            occurrences = SqlaOccurrenceRepository(s)
            occ = occurrences.get(PHRASE_ID)
            assert occ is not None
            occurrences.write_text(
                PHRASE_ID, occ.source_phrase, occ.phrase_position,
                earned_section=CandidateSection.READY, polished=polished, polish_reverted=True,
            )
            s.commit()
        with self._Session() as s:
            occ = SqlaOccurrenceRepository(s).get(PHRASE_ID)
            assert occ is not None
            assert occ.polished_phrase == polished
            assert occ.polish_reverted
            assert occ.phrase.text == SOURCE_TEXT

    def test_new_source_phrase_drops_polish(self) -> None:
        with self._Session() as s:
            occurrences = SqlaOccurrenceRepository(s)
            occ = occurrences.get(PHRASE_ID)
            assert occ is not None
            occurrences.write_text(
                PHRASE_ID, occ.source_phrase, occ.phrase_position,
                earned_section=CandidateSection.READY,
                polished=phrase("The stale air.", "stale"), polish_reverted=True,
            )
            new_phrase = phrase("The air around us was stale", "stale")
            occurrences.write_text(
                PHRASE_ID, new_phrase, DocumentPosition(0, 0, 0, 0, 27),
                earned_section=CandidateSection.READY,
            )
            s.commit()
            occ = occurrences.get(PHRASE_ID)
            assert occ is not None
            assert occ.source_phrase == new_phrase
            assert occ.polished_phrase is None
            assert not occ.polish_reverted

    def test_meaning_and_tts_can_be_dropped(self) -> None:
        with self._Session() as s:
            meanings = SqlaCandidateMeaningRepository(s)
            tts = SqlaCandidateTTSRepository(s)
            meanings.upsert_for_phrase(PHRASE_ID, CandidateMeaning(
                candidate_id=1, meaning="m", translation=None, synonyms=None,
                examples=None, ipa=None, generated_at=_NOW,
            ))
            tts.upsert_for_phrase(
                PHRASE_ID, CandidateTTS(candidate_id=1, audio_path="a.m4a", generated_at=_NOW),
            )
            meanings.delete_by_phrase_id(PHRASE_ID)
            tts.delete_by_phrase_id(PHRASE_ID)
            s.commit()
            assert meanings.get_by_phrase_id(PHRASE_ID) is None
            assert tts.get_by_phrase_id(PHRASE_ID) is None
