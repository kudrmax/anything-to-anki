"""Frozen value object for a candidate fragment."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """A candidate fragment produced by a CandidateSource.

    ``indices`` is the sorted tuple of token indices that the source
    proposes as a meaningful piece containing the target word.
    """

    indices: tuple[int, ...]
    source_name: str
