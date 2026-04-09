"""Fragment selection pipeline orchestrator.

Six named, short steps: generate → clean → filter → score → select → fallback.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.fragment_selection.cleanup.cleaner import (
    RuleDrivenBoundaryCleaner,
)
from backend.domain.services.fragment_selection.registry import (
    build_candidate_sources,
)
from backend.domain.services.fragment_selection.scoring.scorer import (
    DefaultScorer,
    UnknownCounter,
)
from backend.domain.services.fragment_selection.sources.legacy_extractor import (
    LegacyExtractorSource,
)
from backend.domain.services.fragment_selection.utils import count_content_words
from backend.domain.value_objects.fragment_selection_config import (
    FragmentSelectionConfig,
)

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData
    from backend.domain.services.fragment_selection.candidate import Candidate
    from backend.domain.services.fragment_selection.sources.base import (
        CandidateSource,
    )


class FragmentSelector:
    """Selects the best fragment around a target word.

    Steps:
        1. generate candidates from all enabled sources
        2. clean each candidate's edges
        3. filter candidates that lost the target or are too short
        4. score each surviving candidate
        5. return the candidate with the lowest score
        6. if nothing survived, return the cleaned legacy fragment as a
           safety net (when enabled in config)
    """

    def __init__(
        self,
        config: FragmentSelectionConfig | None = None,
    ) -> None:
        self._config = config or FragmentSelectionConfig()
        self._sources: list[CandidateSource] = build_candidate_sources(
            self._config.sources
        )
        self._cleaner = RuleDrivenBoundaryCleaner(self._config.cleanup)
        self._fallback_source = LegacyExtractorSource()

    def select(
        self,
        tokens: list[TokenData],
        target_index: int,
        protected_indices: frozenset[int],
        unknown_counter: UnknownCounter,
    ) -> list[int]:
        raw = self._step1_generate(tokens, target_index)
        cleaned = self._step2_clean(tokens, raw, protected_indices)
        filtered = self._step3_filter(tokens, cleaned, target_index)
        if not filtered:
            return self._step6_fallback(tokens, target_index, protected_indices)
        scorer = DefaultScorer(
            config=self._config.scoring, unknown_counter=unknown_counter
        )
        scored = self._step4_score(tokens, filtered, scorer)
        return self._step5_select_best(scored)

    # ------------------------------------------------------------------ steps

    def _step1_generate(
        self, tokens: list[TokenData], target_index: int
    ) -> list[Candidate]:
        raw: list[Candidate] = []
        for source in self._sources:
            raw.extend(source.generate(tokens, target_index))
        return raw

    def _step2_clean(
        self,
        tokens: list[TokenData],
        candidates: list[Candidate],
        protected: frozenset[int],
    ) -> list[list[int]]:
        return [
            self._cleaner.clean(
                tokens, list(c.indices), protected_indices=protected
            )
            for c in candidates
        ]

    def _step3_filter(
        self,
        tokens: list[TokenData],
        cleaned: list[list[int]],
        target_index: int,
    ) -> list[list[int]]:
        min_content = self._config.cleanup.min_fragment_content_words
        result: list[list[int]] = []
        for indices in cleaned:
            if not indices or target_index not in indices:
                continue
            if count_content_words(tokens, indices) < min_content:
                continue
            result.append(indices)
        return result

    @staticmethod
    def _step4_score(
        tokens: list[TokenData],
        candidates: list[list[int]],
        scorer: DefaultScorer,
    ) -> list[tuple[tuple[int, int, int], list[int]]]:
        return [(scorer.score(c, tokens), c) for c in candidates]

    @staticmethod
    def _step5_select_best(
        scored: list[tuple[tuple[int, int, int], list[int]]],
    ) -> list[int]:
        return min(scored, key=lambda pair: pair[0])[1]

    def _step6_fallback(
        self,
        tokens: list[TokenData],
        target_index: int,
        protected: frozenset[int],
    ) -> list[int]:
        if not self._config.fallback_to_cleaned_legacy:
            return []
        legacy_candidates = list(
            self._fallback_source.generate(tokens, target_index)
        )
        if not legacy_candidates:
            return []
        legacy_indices = list(legacy_candidates[0].indices)
        return self._cleaner.clean(
            tokens, legacy_indices, protected_indices=protected
        )
