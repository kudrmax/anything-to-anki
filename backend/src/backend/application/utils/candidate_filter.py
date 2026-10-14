from __future__ import annotations

from collections.abc import Callable

CandidateFilter = Callable[[list[int]], set[int]]
"""Given ids (of phrases, or of words), returns those still worth writing a result for."""


def keep_all(candidate_ids: list[int]) -> set[int]:
    return set(candidate_ids)
