from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.frequent_word_threshold import FALLBACK_ZIPF

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.entities.word_decision import WordDecision

START_ZIPF: float = FALLBACK_ZIPF
LOWEST_ZIPF: float = 2.5
HIGHEST_ZIPF: float = 5.5
BAND_WIDTH: float = 0.5
MIN_DECISIONS_PER_BAND: int = 4
KNOWN_SHARE: float = 0.5


class FrequencyThresholdCalibrator:
    """Finds the frequency from which the user probably knows a word.

    Starts at START_ZIPF and moves band by band: down while the band just
    below is mostly known, otherwise up while the band just above is mostly
    unknown. A band with too few decisions stops the move — no guessing.
    """

    def calibrate(self, decisions: Sequence[WordDecision]) -> float:
        threshold = START_ZIPF
        while threshold - BAND_WIDTH >= LOWEST_ZIPF:
            share = self._known_share(decisions, threshold - BAND_WIDTH, threshold)
            if share is None or share < KNOWN_SHARE:
                break
            threshold -= BAND_WIDTH
        if threshold != START_ZIPF:
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
