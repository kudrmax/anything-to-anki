from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.generation_result import GenerationResult


class AIService(ABC):
    """Port for AI-powered text generation."""

    @abstractmethod
    def generate_meaning(self, lemma: str, pos: str, context: str) -> GenerationResult:
        """Generate a concise meaning for a word given its context.

        Returns:
            GenerationResult with meaning text and token usage.
        """
