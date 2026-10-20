from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.application.source_intake.source_draft import SourceDraft
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
    def drafts(
        self, content: Content, answers: Answers, source_format: Format, label: str,
    ) -> tuple[SourceDraft, ...]:
        """The sources the content becomes; every question asked is answered."""
