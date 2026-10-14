"""Legacy fragment extractor candidate source.

Self-contained port of the Wave 1 ``FragmentExtractor.extract_indices``
algorithm: subtree escalation with min/max content-word bounds and a
sentence-window fallback. Kept for parity with the frozen regression set.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.fragment_selection.candidate import Candidate
from backend.domain.services.fragment_selection.utils import count_content_words, sentence_of

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData

MIN_FRAGMENT_WORDS: int = 5
MAX_FRAGMENT_WORDS: int = 12
WINDOW_HALF_SIZE: int = 5


class LegacyExtractorSource:
    """Wave 1 fragment-extractor behavior as a candidate source."""

    name: str = "legacy_extractor"

    def generate(
        self,
        tokens: list[TokenData],
        target_index: int,
    ) -> Iterable[Candidate]:
        if not tokens or target_index < 0 or target_index >= len(tokens):
            return
        indices = self._extract(tokens, target_index)
        if not indices or target_index not in indices:
            return
        yield Candidate(indices=tuple(indices), source_name=self.name)

    def _extract(self, tokens: list[TokenData], target_index: int) -> list[int]:
        target = tokens[target_index]

        sentence_indices = self._sentence_window(tokens, target_index)
        if count_content_words(tokens, sentence_indices) <= MAX_FRAGMENT_WORDS:
            return sorted(sentence_indices)

        subtree_indices = self._collect_subtree(tokens, target_index)
        content_count = count_content_words(tokens, subtree_indices)

        if content_count < MIN_FRAGMENT_WORDS and target.head_index != target_index:
            subtree_indices = self._collect_subtree(tokens, target.head_index)
            content_count = count_content_words(tokens, subtree_indices)

        if content_count < MIN_FRAGMENT_WORDS:
            subtree_indices = self._sentence_window(tokens, target_index)

        if count_content_words(tokens, subtree_indices) > MAX_FRAGMENT_WORDS:
            subtree_indices = self._trim_window(tokens, target_index)

        return sorted(subtree_indices)

    @staticmethod
    def _collect_subtree(tokens: list[TokenData], root_index: int) -> set[int]:
        result: set[int] = {root_index}
        stack = list(tokens[root_index].children_indices)
        while stack:
            idx = stack.pop()
            if idx not in result:
                result.add(idx)
                stack.extend(tokens[idx].children_indices)
        return result

    @staticmethod
    def _sentence_window(tokens: list[TokenData], target_index: int) -> set[int]:
        return {t.index for t in sentence_of(tokens, target_index)}

    @staticmethod
    def _trim_window(
        tokens: list[TokenData], target_index: int
    ) -> set[int]:
        sent_tokens = sentence_of(tokens, target_index)
        if not sent_tokens:
            return {target_index}
        left = max(target_index - WINDOW_HALF_SIZE, sent_tokens[0].index)
        right = min(target_index + WINDOW_HALF_SIZE, sent_tokens[-1].index)
        return {t.index for t in sent_tokens if left <= t.index <= right}
