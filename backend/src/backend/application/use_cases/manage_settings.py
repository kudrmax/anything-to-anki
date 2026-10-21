from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.application.dto.settings_dtos import (
    FrequentWordThresholdDTO,
    SettingsDTO,
    UpdateSettingsRequest,
)
from backend.application.utils.settings_writer import (
    ANALYSIS_KEYS,
    BOOL_KEYS,
    FLOAT_KEYS,
    INT_KEYS,
    JSON_LIST_KEYS,
    SETTING_KEYS,
    SettingsWriter,
)
from backend.domain.value_objects.frequent_word_threshold import FREQUENT_WORD_THRESHOLDS

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.sources_rebuild_launcher import SourcesRebuildLauncher
    from backend.domain.ports.unit_of_work import UnitOfWork


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
            for key, default in SETTING_KEYS.items()
        }
        values: dict[str, str | bool | float | int | list[str]] = {}
        for k, v in raw.items():
            if k in BOOL_KEYS:
                values[k] = v.lower() == "true"
            elif k in JSON_LIST_KEYS:
                values[k] = json.loads(v)
            elif k in FLOAT_KEYS:
                values[k] = float(v)
            elif k in INT_KEYS:
                values[k] = int(v)
            else:
                values[k] = v
        return SettingsDTO(**values)  # type: ignore[arg-type]

    def update_settings(self, request: UpdateSettingsRequest) -> SettingsDTO:
        self._save(lambda: self._write_settings(request))
        return self.get_settings()

    def _write_settings(self, request: UpdateSettingsRequest) -> None:
        SettingsWriter(self._settings_repo).write(request)

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
        self._save(lambda: self._settings_repo.set("cefr_level", level))

    def _save(self, write_settings: Callable[[], None]) -> None:
        """Writes in one write transaction; sources are rebuilt after it is committed if a
        setting they depend on changed."""
        with self._unit_of_work.write():
            before = self._rebuild_trigger_values()
            write_settings()
            changed = self._rebuild_trigger_values() != before
        if changed:
            self._rebuild_launcher.rebuild_all()

    def _rebuild_trigger_values(self) -> dict[str, str]:
        return {
            key: self._settings_repo.get(key, SETTING_KEYS[key]) or SETTING_KEYS[key]
            for key in ANALYSIS_KEYS
        }

