from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.ai_outage_recorder import AIOutageRecorder
from backend.infrastructure.persistence.sqla_ai_outage_repository import SqlaAIOutageRepository

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


class SessionAIOutageRecorder(AIOutageRecorder):
    """Commits what each AI call found in its own session: the caller's transaction
    may roll back, the AI's availability stays what the call saw."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def unavailable(self, reason: str) -> None:
        with self._session_factory() as session, session.begin():
            SqlaAIOutageRepository(session).report(reason)

    def answered(self) -> None:
        with self._session_factory() as session, session.begin():
            SqlaAIOutageRepository(session).clear()
