from __future__ import annotations

from enum import Enum


class LevelChangeStage(Enum):
    ANALYSE = "analyse"
    APPLY = "apply"
    FINISH = "finish"


# Shares of the percent, so it goes on about evenly in time (measured on the whole Worm).
ANALYSE_SHARE = 70
APPLY_SHARE = 20
FINISH_SHARE = 10
DONE_PERCENT = 100


def percent(stage: LevelChangeStage, done: int, total: int) -> int:
    """How far a running level change is; it reaches DONE_PERCENT only once committed."""
    part = 0.0 if total == 0 else min(done, total) / total
    match stage:
        case LevelChangeStage.ANALYSE:
            return int(ANALYSE_SHARE * part)
        case LevelChangeStage.APPLY:
            return ANALYSE_SHARE + int(APPLY_SHARE * part)
        case LevelChangeStage.FINISH:
            return ANALYSE_SHARE + APPLY_SHARE
