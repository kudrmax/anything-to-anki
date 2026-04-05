from __future__ import annotations

from pydantic import BaseModel


class GenerateMeaningResponseDTO(BaseModel):
    """Result of AI-powered meaning generation for a single candidate."""

    candidate_id: int
    meaning: str
    tokens_used: int


class GenerateAllMeaningsResultDTO(BaseModel):
    """Aggregate result of generating meanings for multiple candidates."""

    generated: int
    failed: int
    total_tokens_used: int
