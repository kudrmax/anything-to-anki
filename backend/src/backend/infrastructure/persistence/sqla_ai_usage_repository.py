from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func

from backend.domain.ports.ai_usage_repository import AIUsageRepository
from backend.infrastructure.persistence.models import AIUsageModel

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

    from backend.domain.entities.ai_usage_record import AIUsageRecord


class SqlaAIUsageRepository(AIUsageRepository):
    """SQLAlchemy implementation of AIUsageRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, record: AIUsageRecord) -> AIUsageRecord:
        model = AIUsageModel.from_entity(record)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def list_between(self, start: datetime | None, end: datetime) -> list[AIUsageRecord]:
        query = self._session.query(AIUsageModel).filter(AIUsageModel.created_at < end)
        if start is not None:
            query = query.filter(AIUsageModel.created_at >= start)
        models = query.order_by(AIUsageModel.created_at, AIUsageModel.id).all()
        return [m.to_entity() for m in models]

    def first_recorded_at(self) -> datetime | None:
        first: datetime | None = self._session.query(func.min(AIUsageModel.created_at)).scalar()
        return first
