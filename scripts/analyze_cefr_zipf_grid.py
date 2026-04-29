"""Diagnostic: analyze sizes of CEFR × Zipf grid cells in the reference dictionary.

Iterates all unique (lemma, pos) from dict.db, resolves final CEFR via the same
VotingCEFRClassifier as production, gets Zipf from WordfreqFrequencyProvider.

Usage (from project root):
    source .venv/bin/activate && PYTHONPATH=backend/src python scripts/analyze_cefr_zipf_grid.py
"""
from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.dict_cache.cefr_source import DictCacheCEFRSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader
from backend.infrastructure.adapters.wordfreq_frequency_provider import WordfreqFrequencyProvider

# --- config ---

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

CEFR_LEVELS = ["B2", "C1", "C2"]
ZIPF_BINS = [(3.0, 3.5), (3.5, 4.0), (4.0, 4.5), (4.5, 5.0), (5.0, 5.5)]
ZIPF_MIN = 3.0
ZIPF_MAX = 5.5

# Reverse mapping: unified POS (dict.db) → PTB POS (classifier expects)
_UNIFIED_TO_PTB: dict[str, str] = {
    "noun": "NN",
    "verb": "VB",
    "adjective": "JJ",
    "adverb": "RB",
    "exclamation": "UH",
    "modal verb": "MD",
    "preposition": "IN",
    "determiner": "DT",
    "pronoun": "PRP",
    "conjunction": "CC",
}


# --- data ---

@dataclass
class DictEntry:
    lemma: str
    pos: str
    cefr: str
    zipf: float


@dataclass
class FilterStats:
    total_pairs: int = 0
    excluded_phrasal_verb: int = 0
    excluded_cefr_below_b2: int = 0
    excluded_cefr_unknown: int = 0
    excluded_zipf_out_of_range: int = 0
    passed: int = 0


# --- build classifier (same as analyze_known_words.py / container.py) ---

def build_classifier() -> tuple[VotingCEFRClassifier, DictCacheReader]:
    dictionaries_dir = os.environ.get("DICTIONARIES_DIR", "")
    if not dictionaries_dir:
        raise RuntimeError("DICTIONARIES_DIR not set in .env")

    dict_cache_path = Path(dictionaries_dir) / ".cache" / "dict.db"
    reader = DictCacheReader(dict_cache_path)

    cefr_sources: list[CEFRSource] = []
    priority_sources: list[CEFRSource] = []
    for meta in reader.get_cefr_sources():
        src = DictCacheCEFRSource(reader, meta["name"])
        if meta["priority"] == "high":
            priority_sources.append(src)
        else:
            cefr_sources.append(src)
    cefr_sources.append(CefrpyCEFRSource())

    print(f"  CEFR priority sources: {[s.name for s in priority_sources]}")
    print(f"  CEFR regular sources:  {[s.name for s in cefr_sources]}")

    return VotingCEFRClassifier(cefr_sources, priority_sources=priority_sources), reader


# --- load all (lemma, pos) from dict.db ---

def load_all_pairs(dict_db_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(f"file:{dict_db_path}?mode=ro", uri=True)
    rows = conn.execute("SELECT DISTINCT lemma, pos FROM cefr").fetchall()
    conn.close()
    return rows


# --- resolve & filter ---

def resolve_entries(
    pairs: list[tuple[str, str]],
    classifier: VotingCEFRClassifier,
    freq: WordfreqFrequencyProvider,
) -> tuple[list[DictEntry], FilterStats]:
    stats = FilterStats(total_pairs=len(pairs))
    entries: list[DictEntry] = []

    for lemma, unified_pos in pairs:
        if unified_pos == "phrasal verb":
            stats.excluded_phrasal_verb += 1
            continue

        # cefrpy crashes on non-ASCII lemmas (struct.error)
        if not lemma.isascii():
            stats.excluded_cefr_unknown += 1
            continue

        ptb_pos = _UNIFIED_TO_PTB.get(unified_pos, unified_pos)
        try:
            breakdown = classifier.classify_detailed(lemma, ptb_pos)
        except Exception:
            stats.excluded_cefr_unknown += 1
            continue
        cefr_name = breakdown.final_level.name

        if cefr_name == "UNKNOWN":
            stats.excluded_cefr_unknown += 1
            continue
        if cefr_name in ("A1", "A2", "B1"):
            stats.excluded_cefr_below_b2 += 1
            continue

        zipf = freq.get_zipf_value(lemma)
        if zipf < ZIPF_MIN or zipf > ZIPF_MAX:
            stats.excluded_zipf_out_of_range += 1
            continue

        stats.passed += 1
        entries.append(DictEntry(lemma=lemma, pos=unified_pos, cefr=cefr_name, zipf=zipf))

    return entries, stats


# --- reporting ---

def _bin_label(low: float, high: float) -> str:
    return f"{low:.1f}-{high:.1f}"


def _assign_bin(zipf: float) -> str | None:
    for low, high in ZIPF_BINS:
        if low <= zipf < high or (high == ZIPF_MAX and zipf == high):
            return _bin_label(low, high)
    return None


def report_grid(entries: list[DictEntry]) -> None:
    grid: dict[str, dict[str, int]] = {lvl: defaultdict(int) for lvl in CEFR_LEVELS}
    for e in entries:
        b = _assign_bin(e.zipf)
        if b:
            grid[e.cefr][b] += 1

    bin_labels = [_bin_label(l, h) for l, h in ZIPF_BINS]
    header = f"{'':>8s}" + "".join(f" │ {b:>8s}" for b in bin_labels) + " │   TOTAL"
    sep = "─" * len(header)

    print(f"\n{sep}")
    print("  1. GRID: CEFR × Zipf (word counts)")
    print(sep)
    print(header)
    print(sep)

    col_totals: dict[str, int] = defaultdict(int)
    grand_total = 0

    for lvl in CEFR_LEVELS:
        row_total = 0
        row = f"{lvl:>8s}"
        for b in bin_labels:
            count = grid[lvl][b]
            row += f" │ {count:>8d}"
            row_total += count
            col_totals[b] += count
        row += f" │ {row_total:>7d}"
        grand_total += row_total
        print(row)

    print(sep)
    total_row = f"{'TOTAL':>8s}"
    for b in bin_labels:
        total_row += f" │ {col_totals[b]:>8d}"
    total_row += f" │ {grand_total:>7d}"
    print(total_row)
    print(sep)


def report_anomalies(entries: list[DictEntry]) -> None:
    grid: dict[str, dict[str, int]] = {lvl: defaultdict(int) for lvl in CEFR_LEVELS}
    for e in entries:
        b = _assign_bin(e.zipf)
        if b:
            grid[e.cefr][b] += 1

    bin_labels = [_bin_label(l, h) for l, h in ZIPF_BINS]

    print("\n  2. ANOMALIES")
    print("─" * 50)

    small_cells: list[tuple[str, str, int]] = []
    empty_cells: list[tuple[str, str]] = []

    for lvl in CEFR_LEVELS:
        for b in bin_labels:
            count = grid[lvl][b]
            if count == 0:
                empty_cells.append((lvl, b))
            elif count < 20:
                small_cells.append((lvl, b, count))

    if empty_cells:
        print("\n  Empty cells (0 words):")
        for lvl, b in empty_cells:
            print(f"    {lvl} × Zipf {b}")

    if small_cells:
        print("\n  Small cells (< 20 words):")
        for lvl, b, count in small_cells:
            print(f"    {lvl} × Zipf {b}: {count} words")

    if not empty_cells and not small_cells:
        print("\n  No anomalies — all cells have ≥ 20 words.")

    all_counts = []
    for lvl in CEFR_LEVELS:
        for b in bin_labels:
            all_counts.append((lvl, b, grid[lvl][b]))

    min_cell = min(all_counts, key=lambda x: x[2])
    max_cell = max(all_counts, key=lambda x: x[2])
    print(f"\n  Smallest cell: {min_cell[0]} × Zipf {min_cell[1]} = {min_cell[2]} words")
    print(f"  Largest cell:  {max_cell[0]} × Zipf {max_cell[1]} = {max_cell[2]} words")


def report_sanity(stats: FilterStats) -> None:
    print("\n  3. SANITY CHECK (filter breakdown)")
    print("─" * 50)
    print(f"  Total unique (lemma, pos) in dict.db:  {stats.total_pairs}")
    print(f"  Excluded — phrasal verb:               {stats.excluded_phrasal_verb}")
    print(f"  Excluded — CEFR ≤ B1:                  {stats.excluded_cefr_below_b2}")
    print(f"  Excluded — CEFR UNKNOWN:               {stats.excluded_cefr_unknown}")
    print(f"  Excluded — Zipf outside [{ZIPF_MIN}, {ZIPF_MAX}]:    {stats.excluded_zipf_out_of_range}")
    print(f"  ─────────────────────────────────────")
    print(f"  Passed all filters:                    {stats.passed}")


def main() -> None:
    classifier, reader = build_classifier()
    freq = WordfreqFrequencyProvider()

    dictionaries_dir = os.environ.get("DICTIONARIES_DIR", "")
    dict_db_path = Path(dictionaries_dir) / ".cache" / "dict.db"
    print(f"Dict DB: {dict_db_path}")

    pairs = load_all_pairs(dict_db_path)
    print(f"Total (lemma, pos) pairs: {len(pairs)}")
    print("Resolving CEFR + Zipf (this may take a minute)...")

    entries, stats = resolve_entries(pairs, classifier, freq)

    report_grid(entries)
    report_anomalies(entries)
    report_sanity(stats)
    print()


if __name__ == "__main__":
    main()
