from __future__ import annotations

from pydantic import BaseModel


class GenerateAllMeaningsResultDTO(BaseModel):
    """Aggregate result of generating meanings for multiple candidates."""

    generated: int
    failed: int
    total_tokens_used: int
