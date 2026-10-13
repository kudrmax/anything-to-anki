from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.content import Content
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.question import Answers, Question
    from backend.domain.value_objects.source_input import SourceInput


class FormatReader(ABC):
    """Reads an input of one format into content."""

    @property
    @abstractmethod
    def format(self) -> Format: ...

    @abstractmethod
    def questions(self, source_input: SourceInput) -> tuple[Question, ...]:
        """What the user has to choose before the input can be read."""

    @abstractmethod
    def read(self, source_input: SourceInput, answers: Answers) -> Content:
        """Reads the input; every question asked is answered."""
