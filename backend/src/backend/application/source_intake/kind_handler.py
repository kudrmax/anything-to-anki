from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.dto.add_source_dtos import SourcesCreated
    from backend.domain.value_objects.content import Content, Kind
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.question import Answers, Question


class KindHandler(ABC):
    """What the product does with content of one kind: which sources it becomes."""

    @property
    @abstractmethod
    def kind(self) -> Kind: ...

    @abstractmethod
    def questions(self, content: Content) -> tuple[Question, ...]:
        """What the user has to choose before the sources are made."""

    @abstractmethod
    def create(self, content: Content, answers: Answers, source_format: Format) -> SourcesCreated:
        """Makes the sources; every question asked is answered."""
