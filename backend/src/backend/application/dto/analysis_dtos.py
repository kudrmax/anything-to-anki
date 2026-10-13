from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, field_validator

from backend.application.dto.cefr_dtos import CEFRBreakdownDTO
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequent_word_threshold import FALLBACK_ZIPF
from backend.domain.value_objects.phrase_words import PhraseWords
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY, Vocabulary

if TYPE_CHECKING:
    from backend.domain.value_objects.usage_distribution import UsageDistribution


class AnalyzeTextRequest(BaseModel):
    """Settings of the text analysis pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_level: str
    vocabulary: Vocabulary = EMPTY_VOCABULARY
    # Words at least this frequent count as known; None — frequency is ignored.
    frequent_word_zipf: float | None = FALLBACK_ZIPF

    @field_validator("user_level")
    @classmethod
    def validate_user_level(cls, v: str) -> str:
        CEFRLevel.from_str(v)
        return v.strip().upper()


class WordCandidateDTO(BaseModel):
    """Single word candidate in the analysis result."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    lemma: str
    pos: str
    cefr_level: str | None
    zipf_frequency: float
    is_sweet_spot: bool
    context_fragment: str
    phrase_words: PhraseWords
    occurrences: int
    is_phrasal_verb: bool = False
    surface_form: str | None = None
    cefr_breakdown: CEFRBreakdownDTO | None = None
    usage_distribution: dict[str, float] | None = None
    phrase_position: DocumentPositionDTO | None = None
    target_position: DocumentPositionDTO | None = None


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

    text: str
    candidates: list[WordCandidateDTO]
    total_tokens: int
    unique_lemmas: int
