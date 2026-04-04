from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.settings_dtos import SettingsDTO, UpdateSettingsRequest

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository

_DEFAULT_CEFR_LEVEL: str = "B1"
_DEFAULT_DECK_NAME: str = "VocabMiner"


class ManageSettingsUseCase:
    """Gets and updates application settings."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings_repo = settings_repo

    def get_settings(self) -> SettingsDTO:
        cefr_level = self._settings_repo.get("cefr_level", _DEFAULT_CEFR_LEVEL) or _DEFAULT_CEFR_LEVEL
        anki_deck_name = self._settings_repo.get("anki_deck_name", _DEFAULT_DECK_NAME) or _DEFAULT_DECK_NAME
        return SettingsDTO(cefr_level=cefr_level, anki_deck_name=anki_deck_name)

    def update_settings(self, request: UpdateSettingsRequest) -> SettingsDTO:
        if request.cefr_level is not None:
            self._settings_repo.set("cefr_level", request.cefr_level)
        if request.anki_deck_name is not None:
            self._settings_repo.set("anki_deck_name", request.anki_deck_name)
        return self.get_settings()

    # kept for backward-compatibility with existing routes
    def update_cefr_level(self, level: str) -> None:
        self._settings_repo.set("cefr_level", level)
