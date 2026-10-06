from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_meaning_image import CandidateMeaningImage
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import StoredCandidateModel
from backend.infrastructure.persistence.sqla_candidate_meaning_image_repository import (
    SqlaCandidateMeaningImageRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
    s.add(StoredCandidateModel(
        id=CANDIDATE_ID,
        source_id=SOURCE_ID,
        lemma="drain",
        pos="NOUN",
        zipf_frequency=4.0,
        is_sweet_spot=True,
        context_fragment="the drain is blocked",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.LEARN.value,
    ))
    s.flush()
    yield s
    s.close()


@pytest.mark.unit
class TestCandidateMeaningImageRepository:
    def test_upsert_then_get_roundtrip(self, session: Session) -> None:
        repo = SqlaCandidateMeaningImageRepository(session)
        image = CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH)
        repo.upsert(image)
        assert repo.get_by_candidate_id(CANDIDATE_ID) == image

    def test_upsert_replaces_the_previous_image(self, session: Session) -> None:
        repo = SqlaCandidateMeaningImageRepository(session)
        repo.upsert(CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH))
        repo.upsert(CandidateMeaningImage(CANDIDATE_ID, SECOND_PATH))
        assert repo.get_by_candidate_id(CANDIDATE_ID) == CandidateMeaningImage(
            CANDIDATE_ID, SECOND_PATH,
        )

    def test_delete(self, session: Session) -> None:
        repo = SqlaCandidateMeaningImageRepository(session)
        repo.upsert(CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH))
        repo.delete_by_candidate_id(CANDIDATE_ID)
        assert repo.get_by_candidate_id(CANDIDATE_ID) is None

    def test_candidate_carries_its_meaning_image(self, session: Session) -> None:
        SqlaCandidateMeaningImageRepository(session).upsert(
            CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH),
        )
        candidates = SqlaCandidateRepository(session)

        one = candidates.get_by_id(CANDIDATE_ID)
        [many] = candidates.get_by_source(SOURCE_ID)

        expected = CandidateMeaningImage(CANDIDATE_ID, FIRST_PATH)
        assert one is not None
        assert one.meaning_image == expected
        assert many.meaning_image == expected
