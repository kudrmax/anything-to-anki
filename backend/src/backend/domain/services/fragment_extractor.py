from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData

MIN_FRAGMENT_WORDS: int = 3
MAX_FRAGMENT_WORDS: int = 12
WINDOW_HALF_SIZE: int = 5


class FragmentExtractor:
    """Extracts minimal meaningful context fragments around target words.

    Uses dependency tree structure (via TokenData) to find syntactically
    coherent fragments of 3–12 words.
    """

    def extract(self, tokens: list[TokenData], target_index: int) -> str:
        """Extract a context fragment around the token at target_index."""
        if not tokens or target_index < 0 or target_index >= len(tokens):
            return ""

        target = tokens[target_index]

        # Step 1: collect subtree indices of the target token
        subtree_indices = self._collect_subtree(tokens, target_index)
        content_count = self._count_content_words(tokens, subtree_indices)

        # Step 2: if subtree is too small, go up to head
        if content_count < MIN_FRAGMENT_WORDS and target.head_index != target_index:
            subtree_indices = self._collect_subtree(tokens, target.head_index)
            content_count = self._count_content_words(tokens, subtree_indices)

        # Step 3: if still too small, expand to sentence window
        if content_count < MIN_FRAGMENT_WORDS:
            subtree_indices = self._sentence_window(tokens, target_index)

        # Step 4: if too large, trim to window around target
        if self._count_content_words(tokens, subtree_indices) > MAX_FRAGMENT_WORDS:
            subtree_indices = self._trim_window(tokens, target_index, target.sent_index)

        # Build fragment text from sorted indices, preserving original spacing
        sorted_indices = sorted(subtree_indices)
        parts = [tokens[i].text + tokens[i].whitespace_after for i in sorted_indices]
        return "".join(parts).strip()

    def extract_indices(self, tokens: list[TokenData], target_index: int) -> list[int]:
        """Extract fragment and return the token indices (for unknown-word counting)."""
        if not tokens or target_index < 0 or target_index >= len(tokens):
            return []

        target = tokens[target_index]

        subtree_indices = self._collect_subtree(tokens, target_index)
        content_count = self._count_content_words(tokens, subtree_indices)

        if content_count < MIN_FRAGMENT_WORDS and target.head_index != target_index:
            subtree_indices = self._collect_subtree(tokens, target.head_index)
            content_count = self._count_content_words(tokens, subtree_indices)

        if content_count < MIN_FRAGMENT_WORDS:
            subtree_indices = self._sentence_window(tokens, target_index)

        if self._count_content_words(tokens, subtree_indices) > MAX_FRAGMENT_WORDS:
            subtree_indices = self._trim_window(tokens, target_index, target.sent_index)

        return sorted(subtree_indices)

    def _collect_subtree(self, tokens: list[TokenData], root_index: int) -> set[int]:
        """Recursively collect all indices in the subtree rooted at root_index."""
        result: set[int] = {root_index}
        stack = list(tokens[root_index].children_indices)
        while stack:
            idx = stack.pop()
            if idx not in result:
                result.add(idx)
                stack.extend(tokens[idx].children_indices)
        return result

    def _sentence_window(self, tokens: list[TokenData], target_index: int) -> set[int]:
        """Get all token indices in the same sentence as the target."""
        sent = tokens[target_index].sent_index
        return {t.index for t in tokens if t.sent_index == sent}

    def _trim_window(
        self, tokens: list[TokenData], target_index: int, sent_index: int
    ) -> set[int]:
        """Trim to ±WINDOW_HALF_SIZE content words around target, within same sentence."""
        sent_tokens = sorted(
            [t for t in tokens if t.sent_index == sent_index],
            key=lambda t: t.index,
        )
        if not sent_tokens:
            return {target_index}

        left = max(target_index - WINDOW_HALF_SIZE, sent_tokens[0].index)
        right = min(target_index + WINDOW_HALF_SIZE, sent_tokens[-1].index)
        return {t.index for t in sent_tokens if left <= t.index <= right}

    def _count_content_words(self, tokens: list[TokenData], indices: set[int]) -> int:
        """Count non-punctuation, alphabetic tokens in a set of indices."""
        return sum(
            1
            for idx in indices
            if tokens[idx].is_alpha and not tokens[idx].is_punct
        )
