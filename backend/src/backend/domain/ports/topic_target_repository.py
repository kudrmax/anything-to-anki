from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.topic_target import TopicTarget


class TopicTargetRepository(ABC):
    """Port for persisting targets generated for topic sources."""

    @abstractmethod
    def create_batch(self, targets: list[TopicTarget]) -> list[TopicTarget]: ...

    @abstractmethod
    def get_by_source(self, source_id: int) -> list[TopicTarget]:
        """Return targets of the source ordered by position."""

    @abstractmethod
    def has_targets(self, source_id: int) -> bool: ...
