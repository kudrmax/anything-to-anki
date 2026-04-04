from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.settings_dtos import SettingsDTO

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository

_DEFAULT_CEFR_LEVEL: str = "B1"


class ManageSettingsUseCase:
    """Gets and updates application settings."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings_repo = settings_repo

    def get_settings(self) -> SettingsDTO:
        cefr_level = self._settings_repo.get("cefr_level", _DEFAULT_CEFR_LEVEL)
        return SettingsDTO(cefr_level=cefr_level or _DEFAULT_CEFR_LEVEL)

    def update_cefr_level(self, level: str) -> None:
        self._settings_repo.set("cefr_level", level)
