from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.topic_target_repository import TopicTargetRepository
from backend.infrastructure.persistence.models import TopicTargetModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.topic_target import TopicTarget


class SqlaTopicTargetRepository(TopicTargetRepository):
    """SQLAlchemy implementation of TopicTargetRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_batch(self, targets: list[TopicTarget]) -> list[TopicTarget]:
        models = [TopicTargetModel.from_entity(t) for t in targets]
        self._session.add_all(models)
        self._session.flush()
        return [m.to_entity() for m in models]

    def get_by_source(self, source_id: int) -> list[TopicTarget]:
        models = (
            self._session.query(TopicTargetModel)
            .filter(TopicTargetModel.source_id == source_id)
            .order_by(TopicTargetModel.position)
            .all()
        )
        return [m.to_entity() for m in models]

    def has_targets(self, source_id: int) -> bool:
        return (
            self._session.query(TopicTargetModel.id)
            .filter(TopicTargetModel.source_id == source_id)
            .first()
            is not None
        )
