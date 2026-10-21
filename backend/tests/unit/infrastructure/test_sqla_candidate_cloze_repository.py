from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_cloze_repository import (
    SqlaCandidateClozeRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session

CANDIDATE_ID = 1
PHRASE_ID = phrase_id_of(CANDIDATE_ID)
SOURCE_ID = 1


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    insert_word(
        s, CANDIDATE_ID, source_id=SOURCE_ID, lemma="test", phrase_text="a test",
        status="learn", zipf_frequency=4.0, is_sweet_spot=True,
    )
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
        repo = SqlaCandidateClozeRepository(session, SessionChangeRecorder(session))
        cloze = CandidateCloze(
            CANDIDATE_ID, (2, 3), ClozeHintKind.CUSTOM, "своя", "She gave up.",
        )
        repo.upsert_for_phrase(PHRASE_ID, cloze)
        assert repo.get_by_phrase_id(PHRASE_ID) == cloze

    def test_get_returns_none_for_missing(self, session: Session) -> None:
        assert SqlaCandidateClozeRepository(
            session, SessionChangeRecorder(session),
        ).get_by_phrase_id(999) is None

    def test_upsert_overwrites(self, session: Session) -> None:
        repo = SqlaCandidateClozeRepository(session, SessionChangeRecorder(session))
        repo.upsert_for_phrase(PHRASE_ID, _cloze((1,), ClozeHintKind.NONE))
        repo.upsert_for_phrase(PHRASE_ID, _cloze((0,), ClozeHintKind.FIRST_LETTER))
        stored = repo.get_by_phrase_id(PHRASE_ID)
        assert stored is not None
        assert stored.hidden_word_indices == (0,)
        assert stored.hint_kind == ClozeHintKind.FIRST_LETTER

    def test_delete(self, session: Session) -> None:
        repo = SqlaCandidateClozeRepository(session, SessionChangeRecorder(session))
        repo.upsert_for_phrase(PHRASE_ID, _cloze())
        repo.delete_by_phrase_id(PHRASE_ID)
        assert repo.get_by_phrase_id(PHRASE_ID) is None

    def test_delete_missing_is_noop(self, session: Session) -> None:
        SqlaCandidateClozeRepository(
            session, SessionChangeRecorder(session),
        ).delete_by_phrase_id(999)
