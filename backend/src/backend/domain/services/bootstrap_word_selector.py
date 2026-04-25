from __future__ import annotations

import random

from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.value_objects.cefr_level import CEFRLevel

# Zipf band boundaries: [lower, upper)
# Last band [5.0, 5.5] is inclusive on both ends
_ZIPF_BANDS: list[tuple[float, float]] = [
    (3.0, 3.5),
    (3.5, 4.0),
    (4.0, 4.5),
    (4.5, 5.0),
    (5.0, 5.51),  # 5.51 to make 5.5 inclusive
]


def _zipf_band_index(zipf_value: float) -> int | None:
    """Return the band index for a zipf value, or None if outside all bands."""
    for i, (low, high) in enumerate(_ZIPF_BANDS):
        if low <= zipf_value < high:
            return i
    return None


class BootstrapWordSelector:
    """Selects words for the bootstrap calibration screen.

    For each lemma: intersect its CEFR levels with grid_levels, take the minimum.
    Group by (cell_cefr, zipf_band). Pick one random word from each group.
    """

    def select_words(
        self,
        entries: list[BootstrapWordEntry],
        grid_levels: set[CEFRLevel],
        known_lemmas: set[str],
        excluded_lemmas: set[str],
    ) -> list[BootstrapWordEntry]:
        if not entries or not grid_levels:
            return []

        # Step 1: Group entries by lemma, collecting all CEFR levels
        lemma_cefr_levels: dict[str, set[CEFRLevel]] = {}
        lemma_zipf: dict[str, float] = {}
        for entry in entries:
            if entry.lemma in known_lemmas or entry.lemma in excluded_lemmas:
                continue
            if entry.cefr_level not in grid_levels:
                continue
            lemma_cefr_levels.setdefault(entry.lemma, set()).add(entry.cefr_level)
            lemma_zipf[entry.lemma] = entry.zipf_value

        # Step 2: Assign each lemma to a cell (min_cefr, zipf_band)
        cells: dict[tuple[CEFRLevel, int], list[str]] = {}
        for lemma, cefr_levels in lemma_cefr_levels.items():
            cell_cefr = min(cefr_levels, key=lambda lvl: lvl.value)
            band = _zipf_band_index(lemma_zipf[lemma])
            if band is None:
                continue
            cells.setdefault((cell_cefr, band), []).append(lemma)

        # Step 3: Pick one random word from each cell
        result: list[BootstrapWordEntry] = []
        for (cell_cefr, band), lemmas in cells.items():
            chosen_lemma = random.choice(lemmas)
            result.append(
                BootstrapWordEntry(
                    lemma=chosen_lemma,
                    cefr_level=cell_cefr,
                    zipf_value=lemma_zipf[chosen_lemma],
                )
            )

        # Step 4: Shuffle to remove visual grouping
        random.shuffle(result)
        return result
