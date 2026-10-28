from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.constants import (
    DEFAULT_GENERATION_BATCH_SIZE,
    GENERATION_BATCH_SIZE_SETTING,
)

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository


def generation_batch_size(settings_repo: SettingsRepository) -> int:
    """How many cards a run of the next missing ones takes, as the settings say."""
    raw = settings_repo.get(GENERATION_BATCH_SIZE_SETTING)
    return int(raw) if raw and raw.isdigit() else DEFAULT_GENERATION_BATCH_SIZE
