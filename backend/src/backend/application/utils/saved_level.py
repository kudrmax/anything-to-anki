from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import CEFR_LEVEL_SETTING, DEFAULT_CEFR_LEVEL
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository


def saved_level(settings_repo: SettingsRepository) -> CEFRLevel:
    """The user's level as the settings hold it; the default level until one is saved."""
    level = settings_repo.get(CEFR_LEVEL_SETTING, DEFAULT_CEFR_LEVEL) or DEFAULT_CEFR_LEVEL
    return CEFRLevel.from_str(level)
