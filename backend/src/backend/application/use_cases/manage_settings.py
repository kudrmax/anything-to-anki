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
    from backend.application.utils.level_change_launcher import LevelChangeLauncher
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.unit_of_work import UnitOfWork


class ManageSettingsUseCase:
    """Gets and updates application settings. An update that changes what the analysis
    depends on is a level change: it is started, and saved by it once every source is
    rebuilt."""

    def __init__(
        self,
        settings_repo: SettingsRepository,
        unit_of_work: UnitOfWork,
        level_change: LevelChangeLauncher,
    ) -> None:
        self._settings_repo = settings_repo
        self._unit_of_work = unit_of_work
        self._level_change = level_change

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
        writer = SettingsWriter(self._settings_repo)
        if writer.changes_analysis(request):
            self._level_change.start(request)
        else:
            with self._unit_of_work.write():
                writer.write(request)
        return self.get_settings()

    def analysis_keys(self) -> list[str]:
        """Settings whose change analyses every source again: a long operation the user
        should agree to before it starts."""
        return list(ANALYSIS_KEYS)

    def frequent_word_threshold_options(self) -> list[FrequentWordThresholdDTO]:
        return [
            FrequentWordThresholdDTO(
                value=t.key,
                zipf=t.zipf,
                examples=list(t.examples),
            )
            for t in FREQUENT_WORD_THRESHOLDS
        ]
