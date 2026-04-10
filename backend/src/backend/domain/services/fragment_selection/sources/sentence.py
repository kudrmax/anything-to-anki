"""Sentence candidate source — returns the whole sentence containing the target."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.fragment_selection.candidate import Candidate

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData


class SentenceSource:
    """Yields the full sentence containing the target as one candidate."""

    name: str = "sentence"

    def generate(
        self,
        tokens: list[TokenData],
        target_index: int,
    ) -> Iterable[Candidate]:
        sent_index = tokens[target_index].sent_index
        indices = tuple(
            sorted(t.index for t in tokens if t.sent_index == sent_index)
        )
        if target_index in indices:
            yield Candidate(indices=indices, source_name=self.name)
