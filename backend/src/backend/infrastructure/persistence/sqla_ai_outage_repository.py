from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, insert

from backend.domain.ports.ai_outage_repository import AIOutageRepository
from backend.domain.value_objects.ai_outage import AIOutage
from backend.infrastructure.persistence.models import AIOutageModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

OUTAGE_ROW_ID = 1


class SqlaAIOutageRepository(AIOutageRepository):
    """SQLAlchemy implementation of AIOutageRepository: one row while the outage lasts."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self) -> AIOutage | None:
        model = self._session.get(AIOutageModel, OUTAGE_ROW_ID)
        if model is None:
            return None
        return AIOutage(reason=model.reason, since=model.since, vpn_required=model.vpn_required)

    def report(self, reason: str, vpn_required: bool) -> None:
        model = self._session.get(AIOutageModel, OUTAGE_ROW_ID)
        if model is None:
            self._session.execute(insert(AIOutageModel).values(
                id=OUTAGE_ROW_ID, reason=reason, since=datetime.now(tz=UTC),
                vpn_required=vpn_required,
            ))
        else:
            model.reason = reason
            model.vpn_required = vpn_required
        self._session.flush()

    def clear(self) -> None:
        self._session.execute(delete(AIOutageModel))
        self._session.flush()
