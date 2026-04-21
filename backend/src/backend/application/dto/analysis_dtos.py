from __future__ import annotations

from pydantic import BaseModel, field_validator

from backend.application.dto.cefr_dtos import CEFRBreakdownDTO
from backend.domain.value_objects.cefr_level import CEFRLevel


class AnalyzeTextRequest(BaseModel):
    """Input for the text analysis pipeline."""

    raw_text: str
    user_level: str

    @field_validator("user_level")
    @classmethod
    def validate_user_level(cls, v: str) -> str:
        CEFRLevel.from_str(v)
        return v.strip().upper()


class WordCandidateDTO(BaseModel):
    """Single word candidate in the analysis result."""

    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    is_sweet_spot: bool
    context_fragment: str
    fragment_purity: str  # "clean" | "dirty"
    occurrences: int
    is_phrasal_verb: bool = False
    surface_form: str | None = None
    cefr_breakdown: CEFRBreakdownDTO | None = None
    usage_distribution: dict[str, float] | None = None


def dto_to_usage_distribution(
    raw: dict[str, float] | None,
) -> UsageDistribution | None:
    """Map raw usage dict from DTO back to domain UsageDistribution."""
    from backend.domain.value_objects.usage_distribution import UsageDistribution

    if not raw:
        return None
    return UsageDistribution(groups=raw)


class AnalyzeTextResponse(BaseModel):
    """Output of the text analysis pipeline."""

    cleaned_text: str
    candidates: list[WordCandidateDTO]
    total_tokens: int
    unique_lemmas: int
