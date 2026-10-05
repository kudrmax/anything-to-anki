from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import StoredCandidateModel
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
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


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(StoredCandidateModel(
        id=CANDIDATE_ID,
        source_id=SOURCE_ID,
        lemma="test",
        pos="NOUN",
        zipf_frequency=4.0,
        is_sweet_spot=True,
        context_fragment="a test",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.LEARN.value,
    ))
    s.flush()
    yield s
    s.close()


def _cloze(
    indices: tuple[int, ...] = (1,),
    hint_kind: ClozeHintKind = ClozeHintKind.NONE,
    custom_hint: str | None = None,
) -> CandidateCloze:
    return CandidateCloze(CANDIDATE_ID, indices, hint_kind, custom_hint, "a b")


@pytest.mark.unit
class TestCandidateClozeRepository:
    def test_upsert_then_get_roundtrip(self, session: Session) -> None:
        repo = SqlaCandidateClozeRepository(session)
        cloze = CandidateCloze(
            CANDIDATE_ID, (2, 3), ClozeHintKind.CUSTOM, "своя", "She gave up.",
        )
        repo.upsert(cloze)
        assert repo.get_by_candidate_id(CANDIDATE_ID) == cloze

    def test_get_returns_none_for_missing(self, session: Session) -> None:
        assert SqlaCandidateClozeRepository(session).get_by_candidate_id(999) is None

    def test_upsert_overwrites(self, session: Session) -> None:
        repo = SqlaCandidateClozeRepository(session)
        repo.upsert(_cloze((1,), ClozeHintKind.NONE))
        repo.upsert(_cloze((0,), ClozeHintKind.FIRST_LETTER))
        stored = repo.get_by_candidate_id(CANDIDATE_ID)
        assert stored is not None
        assert stored.hidden_word_indices == (0,)
        assert stored.hint_kind == ClozeHintKind.FIRST_LETTER

    def test_delete(self, session: Session) -> None:
        repo = SqlaCandidateClozeRepository(session)
        repo.upsert(_cloze())
        repo.delete_by_candidate_id(CANDIDATE_ID)
        assert repo.get_by_candidate_id(CANDIDATE_ID) is None

    def test_delete_missing_is_noop(self, session: Session) -> None:
        SqlaCandidateClozeRepository(session).delete_by_candidate_id(999)

    def test_candidate_repository_attaches_cloze(self, session: Session) -> None:
        SqlaCandidateClozeRepository(session).upsert(_cloze())
        candidate_repo = SqlaCandidateRepository(session)
        by_id = candidate_repo.get_by_id(CANDIDATE_ID)
        assert by_id is not None
        assert by_id.cloze is not None
        assert candidate_repo.get_by_source(SOURCE_ID)[0].cloze is not None

    def test_candidate_without_cloze_has_none(self, session: Session) -> None:
        candidate_repo = SqlaCandidateRepository(session)
        by_id = candidate_repo.get_by_id(CANDIDATE_ID)
        assert by_id is not None
        assert by_id.cloze is None
        assert candidate_repo.get_by_source(SOURCE_ID)[0].cloze is None
