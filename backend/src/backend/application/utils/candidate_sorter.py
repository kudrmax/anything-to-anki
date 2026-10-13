from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.constants import (
    DEFAULT_USAGE_GROUP_ORDER,
    USAGE_GROUP_ORDER_SETTING,
)
from backend.domain.services import candidate_sorting
from backend.domain.services.candidate_sections import section_of
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder

if TYPE_CHECKING:
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.phrase_words_reader import PhraseWordsReader
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.settings_repository import SettingsRepository


@dataclass(frozen=True)
class ArrangedCandidates:
    """Cards in review order, each with its section."""

    candidates: list[StoredCandidate]
    sections: dict[int, CandidateSection]

    def section(self, candidate: StoredCandidate) -> CandidateSection:
        assert candidate.id is not None
        return self.sections[candidate.id]

    def ready(self) -> list[StoredCandidate]:
        return [c for c in self.candidates if self.section(c) is CandidateSection.READY]


class CandidateSorter:
    """Puts cards in the order the user picked and into sections, by what the user knows now.

    Text order has no sections in its order; decided cards go below pending ones.
    """

    def __init__(
        self,
        settings_repo: SettingsRepository,
        threshold_resolver: FrequentWordThresholdResolver,
        vocabulary: UserVocabulary,
        phrase_words_reader: PhraseWordsReader,
    ) -> None:
        self._settings_repo = settings_repo
        self._threshold_resolver = threshold_resolver
        self._vocabulary = vocabulary
        self._phrase_words_reader = phrase_words_reader

    def arrange(
        self,
        candidates: list[StoredCandidate],
        order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> ArrangedCandidates:
        self._phrase_words_reader.refresh(candidates)
        vocabulary = self._vocabulary.snapshot()
        threshold = self._threshold_resolver.resolve()
        if order == CandidateSortOrder.CHRONOLOGICAL:
            ordered = candidate_sorting.decided_last(
                candidate_sorting.sort_chronologically(candidates),
            )
        elif order == CandidateSortOrder.KEY_WORDS:
            ordered = candidate_sorting.sort_by_key_words(
                candidates, frequent_threshold=threshold, vocabulary=vocabulary,
            )
        else:
            ordered = candidate_sorting.sort_by_relevance(
                candidates,
                usage_order=self._usage_order(),
                frequent_threshold=threshold,
                vocabulary=vocabulary,
            )
        return ArrangedCandidates(
            candidates=ordered,
            sections={
                c.id: section_of(c, vocabulary, threshold)
                for c in ordered if c.id is not None
            },
        )

    def sort(
        self,
        candidates: list[StoredCandidate],
        order: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    ) -> list[StoredCandidate]:
        return self.arrange(candidates, order).candidates

    def _usage_order(self) -> list[str]:
        raw = self._settings_repo.get(USAGE_GROUP_ORDER_SETTING)
        return json.loads(raw) if raw else DEFAULT_USAGE_GROUP_ORDER
