from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.application.constants import (
    CLOZE_DEFAULT_HINT_SETTING,
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
from backend.application.dto.settings_dtos import (
    FrequentWordThresholdDTO,
    SettingsDTO,
    UpdateSettingsRequest,
)
from backend.application.use_cases.generate_tts import ALL_VOICES
from backend.application.utils.anki_note_settings import (
    ANKI_FIELD_DEFAULTS,
    ANKI_NOTE_TYPE_DEFAULTS,
)
from backend.domain.value_objects.frequent_word_threshold import (
    DEFAULT_FREQUENT_WORD_THRESHOLD,
    FREQUENT_WORD_THRESHOLDS,
)
from backend.domain.value_objects.naming_rule import DEFAULT_NAMING_RULE
from backend.domain.value_objects.source_order import (
    DEFAULT_SOURCE_GROUPING,
    DEFAULT_SOURCE_SORT,
    DEFAULT_SOURCE_SORT_DIRECTION,
)

if TYPE_CHECKING:
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.sources_rebuild_launcher import SourcesRebuildLauncher
    from backend.domain.ports.unit_of_work import UnitOfWork

_DEFAULT_CEFR_LEVEL: str = "B1"
_DEFAULT_DECK_NAME: str = "Default"
_DEFAULT_AI_PROVIDER: str = "claude"
_DEFAULT_AI_MODEL: str = "sonnet"
_DEFAULT_ENABLE_DEFINITIONS: str = "true"

_SETTING_KEYS: dict[str, str] = {
    "cefr_level": _DEFAULT_CEFR_LEVEL,
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

_REBUILD_TRIGGER_KEYS: tuple[str, ...] = ("cefr_level", FREQUENT_WORD_THRESHOLD_SETTING)

_BOOL_KEYS: frozenset[str] = frozenset({"enable_definitions"})
_JSON_LIST_KEYS: frozenset[str] = frozenset({"usage_group_order", "tts_enabled_voices"})
_FLOAT_KEYS: frozenset[str] = frozenset({"tts_speed"})
_INT_KEYS: frozenset[str] = frozenset({IMAGES_PER_SOURCE_SETTING})


class ManageSettingsUseCase:
    """Gets and updates application settings."""

    def __init__(
        self,
        settings_repo: SettingsRepository,
        threshold_resolver: FrequentWordThresholdResolver,
        unit_of_work: UnitOfWork,
        rebuild_launcher: SourcesRebuildLauncher,
    ) -> None:
        self._settings_repo = settings_repo
        self._threshold_resolver = threshold_resolver
        self._unit_of_work = unit_of_work
        self._rebuild_launcher = rebuild_launcher

    def get_settings(self) -> SettingsDTO:
        raw: dict[str, str] = {
            key: (self._settings_repo.get(key, default) or default)
            for key, default in _SETTING_KEYS.items()
        }
        values: dict[str, str | bool | float | int | list[str]] = {}
        for k, v in raw.items():
            if k in _BOOL_KEYS:
                values[k] = v.lower() == "true"
            elif k in _JSON_LIST_KEYS:
                values[k] = json.loads(v)
            elif k in _FLOAT_KEYS:
                values[k] = float(v)
            elif k in _INT_KEYS:
                values[k] = int(v)
            else:
                values[k] = v
        return SettingsDTO(**values)  # type: ignore[arg-type]

    def update_settings(self, request: UpdateSettingsRequest) -> SettingsDTO:
        before = self._rebuild_trigger_values()
        for key in _SETTING_KEYS:
            value = getattr(request, key, None)
            if value is not None:
                if key in _BOOL_KEYS:
                    str_value = str(value).lower()
                elif key in _JSON_LIST_KEYS:
                    str_value = json.dumps(value)
                elif key in _FLOAT_KEYS:
                    str_value = str(value)
                else:
                    str_value = str(value)
                self._settings_repo.set(key, str_value)
        self._rebuild_if_changed(before)
        return self.get_settings()

    def frequent_word_threshold_options(self) -> list[FrequentWordThresholdDTO]:
        auto_zipf = self._threshold_resolver.auto_zipf()
        return [
            FrequentWordThresholdDTO(
                value=t.key,
                zipf=auto_zipf if t.is_auto else t.zipf,
                examples=list(t.examples),
            )
            for t in FREQUENT_WORD_THRESHOLDS
        ]

    # kept for backward-compatibility with existing routes
    def update_cefr_level(self, level: str) -> None:
        before = self._rebuild_trigger_values()
        self._settings_repo.set("cefr_level", level)
        self._rebuild_if_changed(before)

    def _rebuild_trigger_values(self) -> dict[str, str]:
        return {
            key: self._settings_repo.get(key, _SETTING_KEYS[key]) or _SETTING_KEYS[key]
            for key in _REBUILD_TRIGGER_KEYS
        }

    def _rebuild_if_changed(self, before: dict[str, str]) -> None:
        if self._rebuild_trigger_values() == before:
            return
        self._unit_of_work.commit()
        self._rebuild_launcher.rebuild_all()

