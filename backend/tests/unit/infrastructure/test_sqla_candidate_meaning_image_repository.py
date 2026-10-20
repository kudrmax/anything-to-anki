from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_meaning_image_repository import (
    SqlaCandidateMeaningImageRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.word_support import insert_word

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

CANDIDATE_ID = 1
SOURCE_ID = 1
FIRST_PATH = "/media/1/1_meaning.aaaaaaaaaa.webp"
SECOND_PATH = "/media/1/1_meaning.bbbbbbbbbb.webp"


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    insert_word(
        s, CANDIDATE_ID, source_id=SOURCE_ID, lemma="drain", phrase_text="the drain is blocked",
        status="learn", zipf_frequency=4.0, is_sweet_spot=True,
    )
    s.flush()
    yield s
    s.close()


def _image(session: Session) -> CandidateMeaningImage | None:
    word = SqlaCandidateRepository(session, SessionChangeRecorder(session)).get_by_id(CANDIDATE_ID)
    assert word is not None
    return word.meaning_image


@pytest.mark.unit
class TestCandidateMeaningImageRepository:
    def test_upsert_then_get_roundtrip(self, session: Session) -> None:
        repo = SqlaCandidateMeaningImageRepository(session, SessionChangeRecorder(session))
        image = CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH)
        repo.upsert(image)
        assert _image(session) == image

    def test_upsert_replaces_the_previous_image(self, session: Session) -> None:
        repo = SqlaCandidateMeaningImageRepository(session, SessionChangeRecorder(session))
        repo.upsert(CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH))
        repo.upsert(CandidateMeaningImage(CANDIDATE_ID, SECOND_PATH))
        assert _image(session) == CandidateMeaningImage(
            CANDIDATE_ID, SECOND_PATH,
        )

    def test_delete(self, session: Session) -> None:
        repo = SqlaCandidateMeaningImageRepository(session, SessionChangeRecorder(session))
        repo.upsert(CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH))
        repo.delete_by_candidate_id(CANDIDATE_ID)
        assert _image(session) is None

    def test_candidate_carries_its_meaning_image(self, session: Session) -> None:
        SqlaCandidateMeaningImageRepository(session, SessionChangeRecorder(session)).upsert(
            CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH),
        )
        candidates = SqlaCandidateRepository(session, SessionChangeRecorder(session))

        one = candidates.get_by_id(CANDIDATE_ID)
        [many] = candidates.get_by_source(SOURCE_ID)

        expected = CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH)
        assert one is not None
        assert one.meaning_image == expected
        assert many.meaning_image == expected
