from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.application.constants import (
    CEFR_LEVEL_SETTING,
    CLOZE_DEFAULT_HINT_SETTING,
    DEFAULT_CEFR_LEVEL,
    DEFAULT_CLOZE_HINT,
    DEFAULT_IMAGES_PER_SOURCE,
    DEFAULT_USAGE_GROUP_ORDER,
    FREQUENT_WORD_THRESHOLD_SETTING,
    IMAGES_PER_SOURCE_SETTING,
    NAMING_RULE_SETTING,
    SOURCE_GROUPING_SETTING,
    SOURCE_SORT_DIRECTION_SETTING,
    SOURCE_SORT_SETTING,
)
from backend.application.use_cases.generate_tts import ALL_VOICES
from backend.application.utils.anki_note_settings import (
    ANKI_FIELD_DEFAULTS,
    ANKI_NOTE_TYPE_DEFAULTS,
)
from backend.domain.value_objects.frequent_word_threshold import DEFAULT_FREQUENT_WORD_THRESHOLD
from backend.domain.value_objects.naming_rule import DEFAULT_NAMING_RULE
from backend.domain.value_objects.source_order import (
    DEFAULT_SOURCE_GROUPING,
    DEFAULT_SOURCE_SORT,
    DEFAULT_SOURCE_SORT_DIRECTION,
)

if TYPE_CHECKING:
    from backend.application.dto.settings_dtos import UpdateSettingsRequest
    from backend.domain.ports.settings_repository import SettingsRepository

_DEFAULT_DECK_NAME: str = "Default"
_DEFAULT_AI_PROVIDER: str = "claude"
_DEFAULT_AI_MODEL: str = "sonnet"
_DEFAULT_ENABLE_DEFINITIONS: str = "true"

SETTING_KEYS: dict[str, str] = {
    CEFR_LEVEL_SETTING: DEFAULT_CEFR_LEVEL,
    FREQUENT_WORD_THRESHOLD_SETTING: DEFAULT_FREQUENT_WORD_THRESHOLD.key,
    "anki_deck_name": _DEFAULT_DECK_NAME,
    "ai_provider": _DEFAULT_AI_PROVIDER,
    "ai_model": _DEFAULT_AI_MODEL,
    **ANKI_NOTE_TYPE_DEFAULTS,
    **ANKI_FIELD_DEFAULTS,
    "enable_definitions": _DEFAULT_ENABLE_DEFINITIONS,
    "usage_group_order": json.dumps(DEFAULT_USAGE_GROUP_ORDER),
    "tts_enabled_voices": json.dumps(ALL_VOICES),
    "tts_speed": "1.0",
    IMAGES_PER_SOURCE_SETTING: str(DEFAULT_IMAGES_PER_SOURCE),
    CLOZE_DEFAULT_HINT_SETTING: DEFAULT_CLOZE_HINT,
    NAMING_RULE_SETTING: DEFAULT_NAMING_RULE,
    SOURCE_GROUPING_SETTING: DEFAULT_SOURCE_GROUPING.value,
    SOURCE_SORT_SETTING: DEFAULT_SOURCE_SORT.value,
    SOURCE_SORT_DIRECTION_SETTING: DEFAULT_SOURCE_SORT_DIRECTION.value,
}

# The settings every source's analysis depends on: changing one is a level change.
ANALYSIS_KEYS: tuple[str, ...] = (CEFR_LEVEL_SETTING, FREQUENT_WORD_THRESHOLD_SETTING)

BOOL_KEYS: frozenset[str] = frozenset({"enable_definitions"})
JSON_LIST_KEYS: frozenset[str] = frozenset({"usage_group_order", "tts_enabled_voices"})
FLOAT_KEYS: frozenset[str] = frozenset({"tts_speed"})
INT_KEYS: frozenset[str] = frozenset({IMAGES_PER_SOURCE_SETTING})


class SettingsWriter:
    """Writes a settings update and tells whether it changes what the analysis depends on."""

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings_repo = settings_repo

    def write(self, request: UpdateSettingsRequest) -> None:
        for key in SETTING_KEYS:
            value = getattr(request, key, None)
            if value is None:
                continue
            if key in BOOL_KEYS:
                self._settings_repo.set(key, str(value).lower())
            elif key in JSON_LIST_KEYS:
                self._settings_repo.set(key, json.dumps(value))
            else:
                self._settings_repo.set(key, str(value))

    def stored(self, key: str) -> str:
        return self._settings_repo.get(key, SETTING_KEYS[key]) or SETTING_KEYS[key]

    def after(self, request: UpdateSettingsRequest, key: str) -> str:
        """What `key` holds once `request` is written."""
        value = getattr(request, key, None)
        return self.stored(key) if value is None else str(value)

    def changes_analysis(self, request: UpdateSettingsRequest) -> bool:
        return any(self.after(request, key) != self.stored(key) for key in ANALYSIS_KEYS)
