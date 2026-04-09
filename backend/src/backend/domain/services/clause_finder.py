from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.token_data import TokenData

# Finite verb tags (have tense / agreement) — Penn Treebank.
_FINITE_TAGS = frozenset({"VBZ", "VBP", "VBD", "MD"})

# Non-finite verb tags (gerund, participle, base form). Level 2 inclusion:
# their subtrees still form meaningful sub-units (`forming me into a genius`,
# `Defamed by the fake news`).
_NONFINITE_TAGS = frozenset({"VBG", "VBN", "VB"})

_VERB_TAGS = _FINITE_TAGS | _NONFINITE_TAGS


class ClauseFinder:
    """Finds candidate 'meaningful pieces' (clause-like sub-units) in a token list.

    A piece is the dependency subtree rooted at a verb token (any form: finite,
    gerund, participle, base). Pieces are restricted to a single sentence to
    avoid crossing sentence boundaries.

    Used by the fragment-selection pipeline to enumerate alternatives for the
    'best fragment containing target' search.
    """

    def find_pieces(self, tokens: list[TokenData]) -> list[list[int]]:
        """Return all candidate piece index lists, sorted by start index."""
        pieces: list[list[int]] = []
        for token in tokens:
            if token.pos != "VERB" or token.tag not in _VERB_TAGS:
                continue
            sent_idx = token.sent_index
            subtree = self._collect_subtree_in_sentence(tokens, token.index, sent_idx)
            if subtree:
                pieces.append(subtree)
        pieces.sort(key=lambda p: p[0] if p else 0)
        return pieces

    @staticmethod
    def _collect_subtree_in_sentence(
        tokens: list[TokenData], root_index: int, sent_idx: int
    ) -> list[int]:
        result: set[int] = set()
        stack = [root_index]
        while stack:
            idx = stack.pop()
            if idx in result:
                continue
            if tokens[idx].sent_index != sent_idx:
                continue
            result.add(idx)
            stack.extend(tokens[idx].children_indices)
        return sorted(result)
