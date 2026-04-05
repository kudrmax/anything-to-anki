from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.prompt_template import PromptTemplate


class PromptRepository(ABC):
    """Port for prompt template persistence."""

    @abstractmethod
    def get_by_key(self, function_key: str) -> PromptTemplate | None: ...

    @abstractmethod
    def list_all(self) -> list[PromptTemplate]: ...

    @abstractmethod
    def update(self, function_key: str, system_prompt: str, user_template: str) -> PromptTemplate: ...
