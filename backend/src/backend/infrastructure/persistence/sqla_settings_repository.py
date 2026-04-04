from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.settings_repository import SettingsRepository
from backend.infrastructure.persistence.models import SettingModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaSettingsRepository(SettingsRepository):
    """SQLAlchemy implementation of SettingsRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: str, default: str | None = None) -> str | None:
        model = self._session.get(SettingModel, key)
        return model.value if model else default

    def set(self, key: str, value: str) -> None:
        model = self._session.get(SettingModel, key)
        if model is None:
            model = SettingModel(key=key, value=value)
            self._session.add(model)
        else:
            model.value = value
        self._session.flush()
