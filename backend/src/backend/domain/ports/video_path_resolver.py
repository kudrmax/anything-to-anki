from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.input_method import InputMethod


class VideoPathResolver(ABC):
    """Resolves video paths between storage (DB) and filesystem representations."""

    @abstractmethod
    def resolve(self, stored_path: str, input_method: InputMethod) -> str:
        """Convert a stored relative video path to an absolute filesystem path."""

    @abstractmethod
    def to_storage_path(self, absolute_path: str, input_method: InputMethod) -> str:
        """Convert an absolute/host path to a relative path for DB storage."""
