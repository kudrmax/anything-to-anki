from __future__ import annotations

from pydantic import BaseModel


class GenerateMeaningResponseDTO(BaseModel):
    """Result of AI-powered meaning generation for a single candidate."""

    candidate_id: int
    meaning: str
    translation: str
    synonyms: str
    examples: str
    ipa: str | None = None
    tokens_used: int


class GenerateAllMeaningsResultDTO(BaseModel):
    """Aggregate result of generating meanings for multiple candidates."""

    generated: int
    failed: int
    total_tokens_used: int
