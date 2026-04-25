from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.entities.bootstrap_index_meta import BootstrapIndexMeta
    from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
    from backend.domain.value_objects.bootstrap_index_status import BootstrapIndexStatus


class BootstrapIndexRepository(ABC):
    """Port for storing and retrieving bootstrap calibration data."""

    @abstractmethod
    def get_meta(self) -> BootstrapIndexMeta: ...

    @abstractmethod
    def set_meta(
        self,
        status: BootstrapIndexStatus,
        error: str | None = None,
        built_at: datetime | None = None,
        word_count: int = 0,
    ) -> None: ...

    @abstractmethod
    def rebuild(self, entries: list[BootstrapWordEntry]) -> None: ...

    @abstractmethod
    def get_all_entries(self) -> list[BootstrapWordEntry]: ...
