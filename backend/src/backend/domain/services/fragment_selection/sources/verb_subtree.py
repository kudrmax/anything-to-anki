"""Verb subtree candidate source — port of ``ClauseFinder.find_pieces``."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.fragment_selection.candidate import Candidate
from backend.domain.services.fragment_selection.utils import (
    collect_subtree_in_sentence,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData

_FINITE_TAGS: frozenset[str] = frozenset({"VBZ", "VBP", "VBD", "MD"})
_NONFINITE_TAGS: frozenset[str] = frozenset({"VBG", "VBN", "VB"})
_VERB_TAGS: frozenset[str] = _FINITE_TAGS | _NONFINITE_TAGS


class VerbSubtreeSource:
    """Yields the dependency subtree of every verb in the target's sentence,
    filtered to subtrees that contain the target."""

    name: str = "verb_subtree"

    def generate(
        self,
        tokens: list[TokenData],
        target_index: int,
    ) -> Iterable[Candidate]:
        for token in tokens:
            if token.pos != "VERB" or token.tag not in _VERB_TAGS:
                continue
            subtree = collect_subtree_in_sentence(
                tokens, token.index, token.sent_index
            )
            if not subtree or target_index not in subtree:
                continue
            yield Candidate(
                indices=tuple(sorted(subtree)),
                source_name=self.name,
            )
