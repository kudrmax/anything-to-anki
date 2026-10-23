from __future__ import annotations

from enum import Enum


class LongOperationStage(Enum):
    ANALYSE = "analyse"
    APPLY = "apply"
    FINISH = "finish"


# Shares of the percent, so it goes on about evenly in time (measured on the whole Worm).
ANALYSE_SHARE = 70
APPLY_SHARE = 20
FINISH_SHARE = 10
DONE_PERCENT = 100


def part_of(done: int, total: int) -> float:
    """The share of a stage done once `done` of its `total` steps are."""
    return 0.0 if total == 0 else min(done, total) / total


def percent(stage: LongOperationStage, part: float) -> int:
    """How far a running long operation is, `part` of its stage done; it reaches
    DONE_PERCENT only once committed."""
    part = min(max(part, 0.0), 1.0)
    match stage:
        case LongOperationStage.ANALYSE:
            return int(ANALYSE_SHARE * part)
        case LongOperationStage.APPLY:
            return ANALYSE_SHARE + int(APPLY_SHARE * part)
        case LongOperationStage.FINISH:
            return ANALYSE_SHARE + APPLY_SHARE
