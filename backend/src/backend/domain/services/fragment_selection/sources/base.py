"""Protocol for candidate sources."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.domain.entities.token_data import TokenData
    from backend.domain.services.fragment_selection.candidate import Candidate


class CandidateSource(Protocol):
    """Generates candidate fragments that contain the target token.

    Implementations are pure: they read tokens and the target index and
    return zero or more candidates. Filtering, cleaning and scoring happen
    later in the pipeline.
    """

    name: str

    def generate(
        self,
        tokens: list[TokenData],
        target_index: int,
    ) -> Iterable[Candidate]:
        ...
