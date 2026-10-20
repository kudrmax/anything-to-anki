from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.settings_repository import SettingsRepository
from backend.domain.value_objects.card_change import LevelChanged
from backend.infrastructure.persistence.models import SettingModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.ports.change_recorder import ChangeRecorder

# The setting of the user's language level: every card's difficulty follows it.
LEVEL_KEY = "cefr_level"


class SqlaSettingsRepository(SettingsRepository):
    """SQLAlchemy implementation of SettingsRepository."""

    def __init__(self, session: Session, recorder: ChangeRecorder) -> None:
        self._session = session
        self._recorder = recorder

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
        if key == LEVEL_KEY:
            self._recorder.record(LevelChanged())
