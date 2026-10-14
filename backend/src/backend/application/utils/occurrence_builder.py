from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.analysis_dtos import dto_to_usage_distribution
from backend.application.dto.cefr_dtos import dto_to_breakdown
from backend.domain.value_objects.built_analysis import BuiltOccurrence, BuiltWord

if TYPE_CHECKING:
    from backend.application.dto.analysis_dtos import OccurrenceDTO, WordDTO


class OccurrenceBuilder:
    """Turns the words of a text analysis into what a rebuild plan is made from."""

    def words(self, words: list[WordDTO]) -> list[BuiltWord]:
        return [self._word(word) for word in words]

    def _word(self, word: WordDTO) -> BuiltWord:
        return BuiltWord(
            lemma=word.lemma,
            is_phrasal_verb=word.is_phrasal_verb,
            pos=word.pos,
            cefr_level=word.cefr_level,
            cefr_breakdown=(
                dto_to_breakdown(word.cefr_breakdown) if word.cefr_breakdown else None
            ),
            zipf_frequency=word.zipf_frequency,
            usage_distribution=dto_to_usage_distribution(word.usage_distribution),
            occurrences=tuple(self._occurrence(o) for o in word.occurrences),
        )

    @staticmethod
    def _occurrence(occurrence: OccurrenceDTO) -> BuiltOccurrence:
        return BuiltOccurrence(
            phrase=occurrence.phrase,
            phrase_position=occurrence.phrase_position.to_position(),
            key=occurrence.key.to_key(),
            fragment_score=occurrence.fragment_score,
        )
