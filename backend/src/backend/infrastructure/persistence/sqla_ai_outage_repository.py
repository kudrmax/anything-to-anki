from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, insert

from backend.domain.ports.ai_outage_repository import AIOutageRepository
from backend.infrastructure.persistence.models import AIOutageModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

OUTAGE_ROW_ID = 1


class SqlaAIOutageRepository(AIOutageRepository):
    """SQLAlchemy implementation of AIOutageRepository: one row while the outage lasts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def reason(self) -> str | None:
        model = self._session.get(AIOutageModel, OUTAGE_ROW_ID)
        return model.reason if model is not None else None

    def report(self, reason: str) -> None:
        model = self._session.get(AIOutageModel, OUTAGE_ROW_ID)
        if model is None:
            self._session.execute(insert(AIOutageModel).values(id=OUTAGE_ROW_ID, reason=reason))
        else:
            model.reason = reason
        self._session.flush()

    def clear(self) -> None:
        self._session.execute(delete(AIOutageModel))
        self._session.flush()
