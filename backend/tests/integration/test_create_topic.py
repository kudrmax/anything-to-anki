from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.create_topic import CreateTopicUseCase
from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.source_role import SourceRole
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def test_topic_keeps_its_query(db_session: Session) -> None:
    use_case = CreateTopicUseCase(SqlaSourceRepository(
        db_session, SessionChangeRecorder(db_session),
    ), MagicMock())
    topic = use_case.execute("job interviews")

    assert topic.id is not None
    stored = SqlaSourceRepository(
        db_session, SessionChangeRecorder(db_session),
    ).get_by_id(topic.id)
    assert stored is not None
    assert (stored.role, stored.topic_query, stored.title) == (
        SourceRole.TOPIC, "job interviews", "job interviews",
    )


def test_empty_topic(db_session: Session) -> None:
    with pytest.raises(InvalidSourceInputError):
        CreateTopicUseCase(SqlaSourceRepository(
            db_session, SessionChangeRecorder(db_session),
        ), MagicMock()).execute("  ")
