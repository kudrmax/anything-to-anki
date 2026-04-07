from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.batch_meaning_result import BatchMeaningResult
    from backend.domain.value_objects.generation_result import GenerationResult


class AIService(ABC):
    """Port for AI-powered text generation."""

    @abstractmethod
    def generate_meaning(self, system_prompt: str, user_prompt: str) -> GenerationResult:
        """Call the AI with the given prompts and return the generated text and token usage."""

    @abstractmethod
    def generate_meanings_batch(
        self, system_prompt: str, user_prompt: str
    ) -> list[BatchMeaningResult]:
        """Batch generation with structured output. Returns meaning+IPA for multiple candidates."""
