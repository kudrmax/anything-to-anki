from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.frequent_word_threshold import (
    AUTO_START_ZIPF,
    THRESHOLD_STEPS,
    step_index,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from backend.domain.entities.word_decision import WordDecision

_ZIPF_STEPS: tuple[float, ...] = tuple(step for step in THRESHOLD_STEPS if step is not None)
LOWEST_ZIPF: float = min(_ZIPF_STEPS)
HIGHEST_ZIPF: float = max(_ZIPF_STEPS)
BAND_WIDTH: float = _ZIPF_STEPS[1] - _ZIPF_STEPS[0]
MIN_DECISIONS_PER_BAND: int = 4
KNOWN_SHARE: float = 0.5


def _check_steps(steps: tuple[float, ...], starts: Iterable[float]) -> None:
    """The calibrator moves band by band from a start, so it lands only on the steps."""
    for start in starts:
        step_index(start)
    banded = tuple(steps[0] + i * (steps[1] - steps[0]) for i in range(len(steps)))
    if steps != banded:
        raise ValueError(f"Threshold steps are not one band apart: {steps}")


_check_steps(_ZIPF_STEPS, AUTO_START_ZIPF.values())


class FrequencyThresholdCalibrator:
    """Finds the frequency from which the user probably knows a word.

    Starts at `start` and moves band by band: down while the band just
    below is mostly known, otherwise up while the band just above is mostly
    unknown. A band with too few decisions stops the move — no guessing.
    """

    def calibrate(self, decisions: Sequence[WordDecision], start: float) -> float:
        step_index(start)
        threshold = start
        while threshold - BAND_WIDTH >= LOWEST_ZIPF:
            share = self._known_share(decisions, threshold - BAND_WIDTH, threshold)
            if share is None or share < KNOWN_SHARE:
                break
            threshold -= BAND_WIDTH
        if threshold != start:
            return threshold
        while threshold + BAND_WIDTH <= HIGHEST_ZIPF:
            share = self._known_share(decisions, threshold, threshold + BAND_WIDTH)
            if share is None or share >= KNOWN_SHARE:
                break
            threshold += BAND_WIDTH
        return threshold

    @staticmethod
    def _known_share(
        decisions: Sequence[WordDecision], low: float, high: float,
    ) -> float | None:
        band = [d for d in decisions if low <= d.zipf_frequency < high]
        if len(band) < MIN_DECISIONS_PER_BAND:
            return None
        return sum(d.is_known for d in band) / len(band)
