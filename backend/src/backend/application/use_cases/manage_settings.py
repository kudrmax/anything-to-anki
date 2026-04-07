from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.settings_dtos import SettingsDTO, UpdateSettingsRequest

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository

_DEFAULT_CEFR_LEVEL: str = "B1"
_DEFAULT_DECK_NAME: str = "Default"
_DEFAULT_NOTE_TYPE: str = "AnythingToAnkiType"
_DEFAULT_AI_PROVIDER: str = "claude"
_DEFAULT_AI_MODEL: str = "sonnet"
_DEFAULT_FIELD_SENTENCE: str = "Sentence"
_DEFAULT_FIELD_TARGET: str = "Target"
_DEFAULT_FIELD_MEANING: str = "Meaning"
_DEFAULT_FIELD_IPA: str = "IPA"
_DEFAULT_ENABLE_DEFINITIONS: str = "true"

_SETTING_KEYS: dict[str, str] = {
    "cefr_level": _DEFAULT_CEFR_LEVEL,
    "anki_deck_name": _DEFAULT_DECK_NAME,
    "ai_provider": _DEFAULT_AI_PROVIDER,
    "ai_model": _DEFAULT_AI_MODEL,
    "anki_note_type": _DEFAULT_NOTE_TYPE,
    "anki_field_sentence": _DEFAULT_FIELD_SENTENCE,
    "anki_field_target_word": _DEFAULT_FIELD_TARGET,
    "anki_field_meaning": _DEFAULT_FIELD_MEANING,
    "anki_field_ipa": _DEFAULT_FIELD_IPA,
    "enable_definitions": _DEFAULT_ENABLE_DEFINITIONS,
}

_BOOL_KEYS: frozenset[str] = frozenset({"enable_definitions"})


class ManageSettingsUseCase:
    """Gets and updates application settings."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings_repo = settings_repo

    def get_settings(self) -> SettingsDTO:
        raw: dict[str, str] = {
            key: (self._settings_repo.get(key, default) or default)
            for key, default in _SETTING_KEYS.items()
        }
        values: dict[str, str | bool] = {
            k: (v.lower() == "true" if k in _BOOL_KEYS else v)
            for k, v in raw.items()
        }
        return SettingsDTO(**values)  # type: ignore[arg-type]

    def update_settings(self, request: UpdateSettingsRequest) -> SettingsDTO:
        for key in _SETTING_KEYS:
            value = getattr(request, key, None)
            if value is not None:
                str_value = str(value).lower() if key in _BOOL_KEYS else str(value)
                self._settings_repo.set(key, str_value)
        return self.get_settings()

    # kept for backward-compatibility with existing routes
    def update_cefr_level(self, level: str) -> None:
        self._settings_repo.set("cefr_level", level)
