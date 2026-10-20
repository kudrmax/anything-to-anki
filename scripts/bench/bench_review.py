"""Measure the review use cases on a copy of a benchmark database.

Run it with `make bench-review`. The input database is never modified: everything happens
on a throwaway copy in the system temp directory.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from backend.domain.exceptions import ActionRefusedError, SourceOperationBusyError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.card_choice import CardChoice, Press
from backend.domain.value_objects.source_scope import SourceScope
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import create_session_factory

OPEN_RUNS = 3
BYTES_PER_MB = 1_000_000
MS = 1000.0
P95 = 95
P99 = 99
PRESS_BUTTONS = (Press.KNOWN, Press.LEARN, Press.SKIP)
COLLECTION_ID_SQL = (
    "SELECT id FROM collections WHERE name = ? AND deleted_at IS NULL ORDER BY id DESC"
)


@dataclass(frozen=True)
class BenchArgs:
    db: Path
    collection: str
    presses: int
    seed: int
    out: Path


@dataclass
class Timings:
    open_review_s: list[float] = field(default_factory=list)
    json_size_mb: float = 0.0
    cards: int = 0
    progress_decided: int = 0
    progress_total: int = 0
    press_decide_ms: list[float] = field(default_factory=list)
    press_reload_ms: list[float] = field(default_factory=list)
    refused: int = 0


def parse_args(argv: list[str] | None = None) -> BenchArgs:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--collection", default="Worm")
    parser.add_argument("--presses", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    ns = parser.parse_args(argv)
    return BenchArgs(ns.db, ns.collection, ns.presses, ns.seed, ns.out)


def copy_to_temp(db: Path, directory: Path) -> Path:
    target = directory / "bench.db"
    origin = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    copy = sqlite3.connect(target)
    try:
        origin.backup(copy)
    finally:
        copy.close()
        origin.close()
    return target


def find_collection_id(db: Path, name: str) -> int:
    connection = sqlite3.connect(db)
    try:
        row = connection.execute(COLLECTION_ID_SQL, (name,)).fetchone()
    finally:
        connection.close()
    if row is None:
        raise SystemExit(f"No collection named {name!r}")
    return int(row[0])


def percentile(values: list[float], percent: int) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)]


def summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    return {
        "median": statistics.median(values),
        "p95": percentile(values, P95),
        "p99": percentile(values, P99),
        "max": max(values),
    }


class ReviewBench:
    def __init__(self, db: Path, scope: SourceScope) -> None:
        self._session_factory = create_session_factory(f"sqlite:///{db}")
        self._container = Container(session_factory=self._session_factory)
        self._scope = scope

    def open_review(self, timings: Timings) -> list[int]:
        """One open of the review in a fresh session; returns the open cards' phrase ids."""
        with self._session_factory() as session:
            began = time.perf_counter()
            review = self._container.get_review_use_case(session).execute(
                self._scope, CandidateSortOrder.RELEVANCE,
            )
            review.model_dump_json()
            timings.open_review_s.append(time.perf_counter() - began)
            body_size = len(review.model_dump_json())
        timings.json_size_mb = body_size / BYTES_PER_MB
        timings.cards = len(review.candidates)
        timings.progress_decided = review.progress.decided
        timings.progress_total = review.progress.total
        return [
            card.phrase_id
            for card in review.candidates
            if card.choice is CardChoice.NONE and not card.is_done
        ]

    def press(self, phrase_id: int, button: Press, timings: Timings) -> bool:
        """False when the app refuses the press (the word is learned from another source)."""
        with self._session_factory() as session:
            began = time.perf_counter()
            try:
                self._container.decide_phrase_use_case(session).decide(phrase_id, button)
            except (ActionRefusedError, SourceOperationBusyError):
                timings.refused += 1
                return False
            session.commit()
            decided = time.perf_counter()
            self._container.get_review_use_case(session).execute(
                self._scope, CandidateSortOrder.RELEVANCE,
            ).model_dump_json()
            reloaded = time.perf_counter()
        timings.press_decide_ms.append((decided - began) * MS)
        timings.press_reload_ms.append((reloaded - decided) * MS)
        return True


def run(args: BenchArgs) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        copy = copy_to_temp(args.db, Path(directory))
        scope = SourceScope.collection(find_collection_id(copy, args.collection))
        bench = ReviewBench(copy, scope)
        timings = Timings()
        open_ids: list[int] = []
        for _ in range(OPEN_RUNS):
            open_ids = bench.open_review(timings)
        rng = random.Random(args.seed)
        rng.shuffle(open_ids)
        for phrase_id in open_ids:
            if len(timings.press_decide_ms) >= args.presses:
                break
            button = PRESS_BUTTONS[len(timings.press_decide_ms) % len(PRESS_BUTTONS)]
            bench.press(phrase_id, button, timings)
    return {
        "db": str(args.db),
        "collection": args.collection,
        "seed": args.seed,
        "cards": timings.cards,
        "open_cards": len(open_ids),
        "json_size_mb": timings.json_size_mb,
        "progress": {"decided": timings.progress_decided, "total": timings.progress_total},
        "open_review_s": {
            "runs": timings.open_review_s,
            "median": statistics.median(timings.open_review_s),
        },
        "presses": len(timings.press_decide_ms),
        "refused_presses": timings.refused,
        "press_decide_ms": {"raw": timings.press_decide_ms, **summary(timings.press_decide_ms)},
        "press_reload_ms": {"raw": timings.press_reload_ms, **summary(timings.press_reload_ms)},
    }


def print_table(result: dict[str, object]) -> None:
    opened = result["open_review_s"]
    assert isinstance(opened, dict)
    print(f"cards {result['cards']} (open {result['open_cards']}), "
          f"json {result['json_size_mb']:.1f} MB, progress {result['progress']}")
    print(f"open_review runs: {[round(x, 2) for x in opened['runs']]} "
          f"median {opened['median']:.2f} s")
    print(f"{'part':<14}{'median':>10}{'p95':>10}{'p99':>10}{'max':>10}  (ms)")
    for key in ("press_decide_ms", "press_reload_ms"):
        part = result[key]
        assert isinstance(part, dict)
        if part.get("median") is not None:
            print(f"{key[:-3]:<14}{part['median']:>10.1f}{part['p95']:>10.1f}"
                  f"{part['p99']:>10.1f}{part['max']:>10.1f}")


def main() -> int:
    args = parse_args()
    result = run(args)
    print_table(result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
