"""Diagnostic: fetch all cards from AnythingToAnki deck via AnkiConnect (read-only)
and analyze their CEFR/Zipf distribution — same analysis as analyze_known_words.py
but for Learned words (cards that made it to Anki).

Requires Anki running with AnkiConnect plugin.

Usage (from project root):
    source .venv/bin/activate && python scripts/analyze_anki_learned.py
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median, quantiles

from dotenv import load_dotenv

from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.anki_connect_connector import AnkiConnectConnector
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.dict_cache.cefr_source import DictCacheCEFRSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader
from backend.infrastructure.adapters.wordfreq_frequency_provider import WordfreqFrequencyProvider

# --- config ---

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DECK_NAME = "AnythingToAnki"
TARGET_FIELD = "Target"
USER_CEFR_LEVEL = "B1"

CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2", "UNKNOWN"]
ZIPF_BIN_SIZE = 0.5
LOW_ZIPF_THRESHOLD = 2.5


# --- data structures ---

@dataclass
class WordInfo:
    lemma: str
    pos: str
    cefr: str
    zipf: float
    decision_method: str


# --- build production classifier (same as container.py) ---

def build_classifier() -> VotingCEFRClassifier:
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

    return VotingCEFRClassifier(cefr_sources, priority_sources=priority_sources)


# --- fetch from Anki ---

def fetch_anki_targets(connector: AnkiConnectConnector) -> list[str]:
    """Fetch all Target field values from the deck. Read-only."""
    note_ids = connector._invoke("findNotes", query=f'deck:"{DECK_NAME}"')
    if not note_ids:
        return []

    notes_info = connector._invoke("notesInfo", notes=note_ids)
    targets: list[str] = []
    for note in notes_info:  # type: ignore[union-attr]
        fields = note.get("fields", {})
        target_field = fields.get(TARGET_FIELD, {})
        value = target_field.get("value", "").strip()
        if value:
            # Strip HTML tags if any
            import re
            clean = re.sub(r"<[^>]+>", "", value).strip()
            if clean:
                targets.append(clean)
    return targets


# --- guess POS for standalone lemma ---

def guess_pos(lemma: str) -> str:
    """Heuristic POS guess for a standalone lemma (no spaCy context).
    The classifier tries with POS first, falls back to any-POS lookup anyway,
    so 'VERB' is a reasonable default for most targets.
    """
    # Multi-word → likely phrasal verb
    if " " in lemma:
        return "VERB"
    return "VERB"


# --- enrich ---

def enrich_words(
    targets: list[str],
    classifier: VotingCEFRClassifier,
    freq: WordfreqFrequencyProvider,
) -> list[WordInfo]:
    result = []
    for target in targets:
        pos = guess_pos(target)
        breakdown = classifier.classify_detailed(target, pos)
        cefr = breakdown.final_level.name
        zipf = freq.get_zipf_value(target)
        result.append(WordInfo(
            lemma=target, pos=pos, cefr=cefr, zipf=zipf,
            decision_method=breakdown.decision_method,
        ))
    return result


# --- reports (same structure as analyze_known_words.py) ---

def _zipf_bin(zipf_val: float) -> str:
    lower = (zipf_val // ZIPF_BIN_SIZE) * ZIPF_BIN_SIZE
    return f"{lower:.1f}-{lower + ZIPF_BIN_SIZE:.1f}"


def _print_header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def _print_bar(label: str, count: int, max_count: int, width: int = 40) -> None:
    bar_len = int(count / max(max_count, 1) * width)
    bar = "█" * bar_len
    print(f"  {label:>10s} │ {bar:<{width}s} {count}")


def report_overall(words: list[WordInfo]) -> None:
    _print_header("1. OVERALL STATISTICS")
    total = len(words)
    matched = sum(1 for w in words if w.cefr != "UNKNOWN")
    unmatched = total - matched
    print(f"  Total learned words (Anki cards): {total}")
    print(f"  Matched to CEFR:       {matched} ({matched / total * 100:.1f}%)")
    print(f"  No CEFR (UNKNOWN):     {unmatched} ({unmatched / total * 100:.1f}%)")

    by_method = defaultdict(int)
    for w in words:
        by_method[w.decision_method] += 1
    print(f"  Decision methods:      {dict(by_method)}")

    zero_zipf = sum(1 for w in words if w.zipf == 0.0)
    if zero_zipf:
        print(f"  Zero Zipf (not in wordfreq): {zero_zipf}")


def report_cefr_distribution(words: list[WordInfo]) -> None:
    _print_header("2. CEFR DISTRIBUTION")
    counts: dict[str, int] = defaultdict(int)
    for w in words:
        counts[w.cefr] += 1

    max_count = max(counts.values()) if counts else 1
    for level in CEFR_ORDER:
        c = counts.get(level, 0)
        if c > 0:
            _print_bar(level, c, max_count)

    print(f"\n  User level: {USER_CEFR_LEVEL}")
    below = sum(counts.get(l, 0) for l in CEFR_ORDER if l <= USER_CEFR_LEVEL and l != "UNKNOWN")
    if below:
        print(f"  ⚠ Words at or below user level ({USER_CEFR_LEVEL}): {below}")


def report_zipf_by_cefr(words: list[WordInfo]) -> None:
    _print_header("3. ZIPF DISTRIBUTION WITHIN EACH CEFR LEVEL")

    by_cefr: dict[str, list[float]] = defaultdict(list)
    for w in words:
        by_cefr[w.cefr].append(w.zipf)

    for level in CEFR_ORDER:
        zipfs = by_cefr.get(level, [])
        if not zipfs:
            continue

        zipfs_sorted = sorted(zipfs)
        print(f"\n  --- {level} ({len(zipfs)} words) ---")
        print(f"  Min: {zipfs_sorted[0]:.2f}  Max: {zipfs_sorted[-1]:.2f}  "
              f"Median: {median(zipfs_sorted):.2f}")

        if len(zipfs_sorted) >= 4:
            q = quantiles(zipfs_sorted, n=4)
            print(f"  Q1(25%): {q[0]:.2f}  Q2(50%): {q[1]:.2f}  Q3(75%): {q[2]:.2f}")

        bins: dict[str, int] = defaultdict(int)
        for z in zipfs:
            bins[_zipf_bin(z)] += 1

        all_bins = sorted(bins.keys(), key=lambda b: float(b.split("-")[0]))
        max_bin = max(bins.values()) if bins else 1
        for b in all_bins:
            _print_bar(b, bins[b], max_bin)


def report_boundary_estimation(words: list[WordInfo]) -> None:
    _print_header("4. BOUNDARY ESTIMATION PER CEFR LEVEL")

    by_cefr: dict[str, list[float]] = defaultdict(list)
    for w in words:
        if w.cefr != "UNKNOWN":
            by_cefr[w.cefr].append(w.zipf)

    for level in ["B2", "C1", "C2"]:
        zipfs = by_cefr.get(level, [])
        if len(zipfs) < 5:
            print(f"\n  {level}: too few words ({len(zipfs)}) for boundary estimation")
            continue

        zipfs_sorted = sorted(zipfs)
        med = median(zipfs_sorted)
        q1 = quantiles(zipfs_sorted, n=4)[0] if len(zipfs_sorted) >= 4 else zipfs_sorted[0]

        print(f"\n  --- {level} ({len(zipfs)} words) ---")
        print(f"  Median Zipf:           {med:.2f}")
        print(f"  25th percentile Zipf:  {q1:.2f}")

        above = sum(1 for z in zipfs if z >= med)
        below = sum(1 for z in zipfs if z < med)
        print(f"  Above median:  {above}   Below median:  {below}")

        if zipfs_sorted[-1] > zipfs_sorted[0]:
            midpoint = (zipfs_sorted[0] + zipfs_sorted[-1]) / 2
            in_upper = sum(1 for z in zipfs if z >= midpoint)
            pct = in_upper / len(zipfs) * 100
            print(f"  In upper half of range ({midpoint:.1f}+): {in_upper} ({pct:.0f}%)")
            if pct > 65:
                print(f"  → Signal: STRONG concentration in upper Zipf")
            elif pct > 55:
                print(f"  → Signal: moderate concentration in upper Zipf")
            else:
                print(f"  → Signal: no clear concentration")


def report_anomalies(words: list[WordInfo]) -> None:
    _print_header("5. ANOMALIES")

    low_zipf = sorted(
        [w for w in words if w.zipf < LOW_ZIPF_THRESHOLD and w.cefr != "UNKNOWN"],
        key=lambda w: w.zipf,
    )
    print(f"\n  5a. Learned words with Zipf < {LOW_ZIPF_THRESHOLD} (rare but learned):")
    if low_zipf:
        for w in low_zipf:
            print(f"      {w.lemma:<25s} CEFR={w.cefr}  Zipf={w.zipf:.2f}  ({w.decision_method})")
    else:
        print(f"      (none)")

    unknown = sorted([w for w in words if w.cefr == "UNKNOWN"], key=lambda w: w.lemma)
    print(f"\n  5b. Learned words without CEFR level ({len(unknown)}):")
    if unknown:
        for w in unknown:
            zipf_note = f"Zipf={w.zipf:.2f}" if w.zipf > 0 else "not in wordfreq"
            print(f"      {w.lemma:<25s} {zipf_note}")
    else:
        print(f"      (none)")

    user_levels = {"A1", "A2", USER_CEFR_LEVEL}
    below_level = sorted(
        [w for w in words if w.cefr in user_levels],
        key=lambda w: (w.cefr, w.lemma),
    )
    print(f"\n  5c. Learned words at or below user level ({USER_CEFR_LEVEL}):")
    if below_level:
        for w in below_level:
            print(f"      {w.lemma:<25s} CEFR={w.cefr}  Zipf={w.zipf:.2f}  ({w.decision_method})")
    else:
        print(f"      (none)")


def report_verdict(words: list[WordInfo]) -> None:
    _print_header("6. VERDICT SUMMARY")

    by_cefr: dict[str, list[float]] = defaultdict(list)
    for w in words:
        if w.cefr != "UNKNOWN":
            by_cefr[w.cefr].append(w.zipf)

    signals: list[str] = []
    for level in ["B2", "C1"]:
        zipfs = by_cefr.get(level, [])
        if len(zipfs) < 10:
            continue
        zipfs_sorted = sorted(zipfs)
        midpoint = (zipfs_sorted[0] + zipfs_sorted[-1]) / 2
        in_upper = sum(1 for z in zipfs if z >= midpoint)
        pct = in_upper / len(zipfs) * 100
        signals.append(f"{level}: {pct:.0f}% in upper Zipf half")

    print()
    for s in signals:
        print(f"  {s}")

    if signals:
        pcts = [float(s.split(":")[1].strip().rstrip("% in upper Zipf half")) for s in signals]
        avg_pct = sum(pcts) / len(pcts)
        print()
        if avg_pct > 65:
            print("  ✅ BOUNDARY IS CLEARLY VISIBLE — bootstrap + Zipf-penalty is viable")
        elif avg_pct > 55:
            print("  ⚠ BOUNDARY IS BLURRY — bootstrap possible, moderate expectations")
        else:
            print("  ❌ NO CLEAR SIGNAL — Zipf is a poor predictor for this user")


def main() -> None:
    print(f"Deck: {DECK_NAME}")
    print(f"User CEFR level: {USER_CEFR_LEVEL}")

    # 1. Connect to Anki
    connector = AnkiConnectConnector()
    if not connector.is_available():
        print("\nERROR: AnkiConnect not available. Is Anki running?")
        sys.exit(1)

    print(f"AnkiConnect version: {connector.get_version()}")

    # 2. Fetch targets
    targets = fetch_anki_targets(connector)
    if not targets:
        print(f"\nERROR: No cards found in deck '{DECK_NAME}'")
        sys.exit(1)

    # Deduplicate (same target can appear in multiple cards)
    unique_targets = sorted(set(targets))
    print(f"\nFetched {len(targets)} cards, {len(unique_targets)} unique targets")

    # 3. Build classifier
    classifier = build_classifier()
    freq = WordfreqFrequencyProvider()

    # 4. Enrich & report
    words = enrich_words(unique_targets, classifier, freq)

    report_overall(words)
    report_cefr_distribution(words)
    report_zipf_by_cefr(words)
    report_boundary_estimation(words)
    report_anomalies(words)
    report_verdict(words)

    print()


if __name__ == "__main__":
    main()
