"""The review header of a set: progress, status and words to learn from the stored
projection."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.source_scope import SourceScope
from backend.infrastructure.api.dependencies import get_container

from tests.projection_support import rebuild_projection
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from backend.application.dto.review_dtos import ReviewHeaderDTO
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

GLARE, SPARK = 1, 2
SCOPE = SourceScope.source(1)


@pytest.fixture()
def cards(db_session: Session, source_id: int) -> Session:
    insert_word(db_session, GLARE, source_id=source_id, lemma="glare")
    insert_word(db_session, SPARK, source_id=source_id, lemma="spark")
    db_session.commit()
    rebuild_projection(db_session)
    return db_session


def _header(session: Session) -> ReviewHeaderDTO:
    return get_container().review_header(session).of(SCOPE)


def test_the_header_counts_the_set(cards: Session) -> None:
    header = _header(cards)
    assert (header.scope, header.status, header.learn_count) == ("source-1", "done", 0)
    assert (header.progress.decided, header.progress.total) == (0, 2)
    assert header.busy is False

    get_container().decide_phrase_use_case(cards).decide(phrase_id_of(GLARE), Press.LEARN)

    header = _header(cards)
    assert (header.progress.decided, header.progress.total) == (1, 2)
    assert header.learn_count == 1

