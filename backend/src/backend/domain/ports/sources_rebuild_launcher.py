from __future__ import annotations

from abc import ABC, abstractmethod


class SourcesRebuildLauncher(ABC):
    """Port for rebuilding every source in the background."""

    @abstractmethod
    def rebuild_all(self) -> None:
        """Ask for a Rebuild without open cards of each source that can be rebuilt, one after
        another. Returns at once; the settings that asked for it are already committed."""
