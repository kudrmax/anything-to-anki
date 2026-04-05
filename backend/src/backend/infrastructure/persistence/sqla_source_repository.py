from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.source_repository import SourceRepository
from backend.infrastructure.persistence.models import SourceModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.entities.source import Source
    from backend.domain.value_objects.source_status import SourceStatus


class SqlaSourceRepository(SourceRepository):
    """SQLAlchemy implementation of SourceRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, source: Source) -> Source:
        model = SourceModel.from_entity(source)
        self._session.add(model)
        self._session.flush()
        return model.to_entity()

    def get_by_id(self, source_id: int) -> Source | None:
        model = self._session.get(SourceModel, source_id)
        return model.to_entity() if model else None

    def list_all(self) -> list[Source]:
        models = self._session.query(SourceModel).order_by(SourceModel.created_at.desc()).all()
        return [m.to_entity() for m in models]

    def delete(self, source_id: int) -> None:
        model = self._session.get(SourceModel, source_id)
        if model is not None:
            self._session.delete(model)
            self._session.flush()

    def update_status(
        self,
        source_id: int,
        status: SourceStatus,
        *,
        cleaned_text: str | None = None,
        error_message: str | None = None,
    ) -> None:
        model = self._session.get(SourceModel, source_id)
        if model is None:
            return
        model.status = status.value
        if cleaned_text is not None:
            model.cleaned_text = cleaned_text
        if error_message is not None:
            model.error_message = error_message
        self._session.flush()
