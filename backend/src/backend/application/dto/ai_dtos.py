from __future__ import annotations

from pydantic import BaseModel

from backend.application.dto.review_dtos import ReviewUpdateDTO  # noqa: TC001 — pydantic field


class GenerateMeaningResponseDTO(BaseModel):
    """Result of AI-powered meaning generation for a single candidate; `update`: what
    changed in the open review it was made on."""

    candidate_id: int
    meaning: str
    translation: str
    synonyms: str
    examples: str
    ipa: str | None = None
    tokens_used: int
    update: ReviewUpdateDTO | None = None


class GenerateAllMeaningsResultDTO(BaseModel):
    """Aggregate result of generating meanings for multiple candidates."""

    generated: int
    failed: int
    total_tokens_used: int
