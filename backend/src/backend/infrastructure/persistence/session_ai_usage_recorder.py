from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.ai_usage_recorder import AIUsageRecorder
from backend.infrastructure.persistence.sqla_ai_usage_repository import SqlaAIUsageRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

    from backend.domain.entities.ai_usage_record import AIUsageRecord


class SessionAIUsageRecorder(AIUsageRecorder):
    """Commits each usage record in its own session.

    The caller's transaction may still roll back after the AI call;
    the tokens were spent either way, so the record must survive it.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(self, record: AIUsageRecord) -> None:
        with self._session_factory() as session, session.begin():
            SqlaAIUsageRepository(session).add(record)
