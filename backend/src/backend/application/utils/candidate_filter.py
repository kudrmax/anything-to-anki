from __future__ import annotations

from collections.abc import Callable

CandidateFilter = Callable[[list[int]], set[int]]
"""Given candidate ids, returns those still worth writing a result for."""


def keep_all(candidate_ids: list[int]) -> set[int]:
    return set(candidate_ids)
