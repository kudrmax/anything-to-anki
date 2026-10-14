from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, InstanceOf, field_validator

from backend.application.dto.cefr_dtos import CEFRBreakdownDTO
from backend.application.dto.document_dtos import DocumentPositionDTO
from backend.domain.entities.occurrence import OccurrenceKey
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.frequent_word_threshold import FALLBACK_ZIPF
from backend.domain.value_objects.phrase import Phrase
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


class OccurrenceKeyDTO(BaseModel):
    """Where the target starts: block, line and character of that line."""

    block: int
    line: int
    char: int

    @staticmethod
    def from_key(key: OccurrenceKey) -> OccurrenceKeyDTO:
        return OccurrenceKeyDTO(block=key.block, line=key.line, char=key.char)

    def to_key(self) -> OccurrenceKey:
        return OccurrenceKey(block=self.block, line=self.line, char=self.char)


class OccurrenceDTO(BaseModel):
    """One place of a word in the text: its phrase there and how good that phrase is.

    A lower `fragment_score` is a better phrase.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    phrase: InstanceOf[Phrase]
    phrase_position: DocumentPositionDTO
    key: OccurrenceKeyDTO
    fragment_score: float


class WordDTO(BaseModel):
    """A word worth learning in the analysed text, with every place it occurs, in reading
    order."""

    lemma: str
    is_phrasal_verb: bool = False
    pos: str
    cefr_level: str | None
    cefr_breakdown: CEFRBreakdownDTO | None = None
    zipf_frequency: float
    usage_distribution: dict[str, float] | None = None
    occurrences: list[OccurrenceDTO]


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
    words: list[WordDTO]
    total_tokens: int
    unique_lemmas: int
