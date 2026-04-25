from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.bootstrap_index_meta import BootstrapIndexMeta  # noqa: TC001
from backend.domain.ports.bootstrap_index_repository import BootstrapIndexRepository
from backend.domain.value_objects.bootstrap_index_status import BootstrapIndexStatus
from backend.infrastructure.persistence.models import (
    BootstrapIndexMetaModel,
    BootstrapWordCellModel,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.orm import Session

    from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry


class SqlaBootstrapIndexRepository(BootstrapIndexRepository):
    """SQLAlchemy implementation of BootstrapIndexRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_meta(self) -> BootstrapIndexMeta:
        model = self._session.get(BootstrapIndexMetaModel, 1)
        if model is None:
            return BootstrapIndexMeta(
                status=BootstrapIndexStatus.NONE,
                error=None,
                built_at=None,
                word_count=0,
            )
        return model.to_entity()

    def set_meta(
        self,
        status: BootstrapIndexStatus,
        error: str | None = None,
        built_at: datetime | None = None,
        word_count: int = 0,
    ) -> None:
        model = self._session.get(BootstrapIndexMetaModel, 1)
        if model is None:
            model = BootstrapIndexMetaModel(id=1)
            self._session.add(model)
        model.status = status.value
        model.error = error
        model.built_at = built_at
        model.word_count = word_count
        self._session.flush()

    def rebuild(self, entries: list[BootstrapWordEntry]) -> None:
        self._session.query(BootstrapWordCellModel).delete()
        for entry in entries:
            model = BootstrapWordCellModel(
                lemma=entry.lemma,
                cefr_level=entry.cefr_level.name,
                zipf_value=entry.zipf_value,
            )
            self._session.add(model)
        self._session.flush()

    def get_all_entries(self) -> list[BootstrapWordEntry]:
        models = self._session.query(BootstrapWordCellModel).all()
        return [m.to_entity() for m in models]
