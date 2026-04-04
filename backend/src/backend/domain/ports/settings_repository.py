from __future__ import annotations

from abc import ABC, abstractmethod


class SettingsRepository(ABC):
    """Port for persisting application settings (key-value)."""

    @abstractmethod
    def get(self, key: str, default: str | None = None) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str) -> None: ...
