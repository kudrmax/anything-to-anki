from __future__ import annotations

from enum import Enum


class CalibrationOrder(Enum):
    """Which words calibration asks about, and in what order.

    REVIEW: the words Review would suggest, in Review's order: common ones first.
        This is the default.
    SPREAD: one random word per CEFR level and frequency band, shuffled.
    """

    REVIEW = "review"
    SPREAD = "spread"
