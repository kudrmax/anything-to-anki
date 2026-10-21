"""Measure the review on a copy of a benchmark database, the way the app serves it: the start
(migrations and the projection rebuilt), opening a review in each order, windows of its
list, presses with their update, the most frequent lemma, the ✨ counts and the texts, a
whole-book ✨ run and a chapter re-cut while a review is open.

Run it with `make bench-review`. The input database is never modified: everything happens
on a throwaway copy in the system temp directory. Each measurement runs once; percentiles
are over the presses and windows of that one run.
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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from backend.application.dto.candidate_dtos import SelectionDTO
from backend.application.dto.review_dtos import (
    OpenReviewRequest,
    ReviewContext,
    ReviewUpdateDTO,
)
from backend.domain.exceptions import ActionRefusedError, DomainError, SourceOperationBusyError
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.document import Paragraph
from backend.domain.value_objects.generation_kind import GenerationKind
from backend.domain.value_objects.generation_scope import GenerationScope
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.source_scope import SourceScope
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import (
    create_session_factory,
    open_query_only,
    run_alembic_migrations,
)
from backend.infrastructure.persistence.sqla_document_repository import SqlaDocumentRepository
from backend.infrastructure.persistence.sqla_unit_of_work import BEGIN_IMMEDIATE
from backend.infrastructure.startup_heap import freeze_startup_heap
from pydantic import BaseModel
from sqlalchemy import Engine, event

if TYPE_CHECKING:
    from collections.abc import Callable

BYTES_PER_KB = 1_000
MS = 1000.0
P95 = 95
P99 = 99
PRESS_BUTTONS = (Press.KNOWN, Press.LEARN, Press.SKIP)
SERVED_ROWS = 200
WINDOWS = 20
WINDOW_ROWS = 50
# Lines of a chapter tried for a word to add from its text.
ADD_TRIES = 20
# What a whole-book ✨ run queues for every card: its meaning and its speech.
RUN_KINDS = (GenerationKind.MEANING, GenerationKind.TTS)
COLLECTION_ID_SQL = (
    "SELECT id FROM collections WHERE name = ? AND deleted_at IS NULL ORDER BY id DESC"
)
SOURCES_SQL = "SELECT id FROM sources WHERE collection_id = ? ORDER BY id"
OPEN_CARDS_SQL = (
    "SELECT cs.phrase_id FROM card_states cs JOIN sources s ON s.id = cs.source_id"
    " WHERE s.collection_id = ? AND NOT cs.removed AND NOT cs.is_done ORDER BY cs.phrase_id"
)
HEAVIEST_LEMMA_SQL = (
    "SELECT cs.lemma, COUNT(*) AS n FROM card_states cs JOIN sources s ON s.id = cs.source_id"
    " WHERE s.collection_id = ? AND NOT cs.removed GROUP BY cs.lemma ORDER BY n DESC LIMIT 1"
)
OPEN_CARD_OF_LEMMA_SQL = (
    "SELECT cs.phrase_id FROM card_states cs JOIN sources s ON s.id = cs.source_id"
    " WHERE s.collection_id = ? AND cs.lemma = ? AND NOT cs.removed AND NOT cs.is_done"
    " ORDER BY cs.phrase_id LIMIT 1"
)
CARD_OF_SOURCE_SQL = (
    "SELECT phrase_id FROM card_states WHERE source_id = ? AND NOT removed"
    " ORDER BY phrase_id LIMIT 1"
)
JOBS_SQL = "SELECT COUNT(*) FROM jobs WHERE status IN ('queued', 'running')"


@dataclass(frozen=True)
class BenchArgs:
    db: Path
    collection: str
    presses: int
    seed: int
    out: Path


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
    origin = open_query_only(str(db))
    copy = sqlite3.connect(target)
    try:
        origin.backup(copy)
    finally:
        copy.close()
        origin.close()
    return target


class Rows:
    """Read-only SQL on the copy, for choosing what to measure."""

    def __init__(self, db: Path) -> None:
        self._db = db

    def all(self, sql: str, *params: object) -> list[tuple[object, ...]]:
        connection = sqlite3.connect(self._db)
        try:
            return list(connection.execute(sql, params))
        finally:
            connection.close()

    def ints(self, sql: str, *params: object) -> list[int]:
        return [int(str(row[0])) for row in self.all(sql, *params)]


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


def kb(model: BaseModel) -> float:
    return len(model.model_dump_json()) / BYTES_PER_KB


def timed[T](work: Callable[[], T]) -> tuple[T, float]:
    """What `work` gives and how long it took, in ms."""
    began = time.perf_counter()
    result = work()
    return result, (time.perf_counter() - began) * MS


class WriteTransactions:
    """How long each write transaction on the engine held the writer: from its BEGIN
    IMMEDIATE to its commit or rollback."""

    def __init__(self, engine: Engine) -> None:
        self._began: float | None = None
        self.held_ms: list[float] = []
        event.listen(engine, "before_cursor_execute", self._begin)
        event.listen(engine, "commit", self._end)
        event.listen(engine, "rollback", self._end)

    def _begin(self, *args: object) -> None:
        statement = args[2]
        if isinstance(statement, str) and statement.startswith(BEGIN_IMMEDIATE):
            self._began = time.perf_counter()

    def _end(self, *_args: object) -> None:
        if self._began is not None:
            self.held_ms.append((time.perf_counter() - self._began) * MS)
            self._began = None


class ReviewBench:
    """The use cases of the review on one container, as one app process holds them: the
    open reviews live in its memory."""

    def __init__(self, db: Path, collection_id: int) -> None:
        self._db_url = f"sqlite:///{db}"
        self._session_factory = create_session_factory(self._db_url)
        self._container = Container(session_factory=self._session_factory)
        self.writes = WriteTransactions(self._session_factory.kw["bind"])
        self.scope = SourceScope.collection(collection_id)

    def start(self) -> dict[str, float]:
        """The app's start: migrations, the projection computed anew, then what start-up
        made frozen out of the garbage collector's walks, as the app's lifespan does."""
        _, migrations = timed(lambda: run_alembic_migrations(self._db_url))
        rebuild = self.rebuild()
        freeze_startup_heap()
        return {"migrations_s": migrations / MS, "startup_rebuild_s": rebuild / MS}

    def rebuild(self) -> float:
        return timed(self._container.rebuild_card_states)[1]

    def open(self, sort: CandidateSortOrder) -> tuple[ReviewUpdateDTO, float, float]:
        """A review opened, to its answer serialised: the answer, ms and KB."""
        with self._session_factory() as session:
            use_case = self._container.open_review_use_case(session)

            def opened() -> tuple[ReviewUpdateDTO, str]:
                answer = use_case.execute(OpenReviewRequest(scope=self.scope.token, sort=sort))
                return answer, answer.model_dump_json()

            (answer, body), ms = timed(opened)
        return answer, ms, len(body) / BYTES_PER_KB

    def rows(self, ctx: ReviewContext, start: int, count: int) -> tuple[ReviewUpdateDTO, float]:
        with self._session_factory() as session:
            window = self._container.review_window_use_case(session)
            return timed(lambda: _serialised(window.rows(ctx, start, count)))

    def around(self, ctx: ReviewContext, phrase_id: int) -> tuple[ReviewUpdateDTO, float]:
        with self._session_factory() as session:
            window = self._container.review_window_use_case(session)
            return timed(lambda: _serialised(window.around(ctx, phrase_id)))

    def changes(self, ctx: ReviewContext) -> tuple[ReviewUpdateDTO, float]:
        with self._session_factory() as session:
            window = self._container.review_window_use_case(session)
            return timed(lambda: _serialised(window.changes(ctx)))

    def press(
        self, ctx: ReviewContext, phrase_id: int, button: Press,
    ) -> tuple[ReviewUpdateDTO, float, float] | None:
        """A press through ReviewMutation, as the route makes it: the answer, the ms of the
        decision with its projection, and the ms of the rest (the update built and
        serialised). None when the app refuses the press."""
        with self._session_factory() as session:
            decide = self._container.decide_phrase_use_case(session)
            mutation = self._container.review_mutation(session)
            decided: list[float] = []

            def action() -> None:
                decided.append(timed(lambda: decide.decide(phrase_id, button))[1])

            try:
                answer, total = timed(
                    lambda: _serialised(mutation.press(ctx, phrase_id, action)),
                )
            except (ActionRefusedError, SourceOperationBusyError):
                return None
        return answer, decided[0], total - decided[0]

    def generation_status(self) -> tuple[float, float]:
        """The ✨ counts of the set: ms and KB."""
        with self._session_factory() as session:
            use_case = self._container.get_generation_status_use_case(session)
            status, ms = timed(lambda: _serialised(use_case.execute(self.scope)))
        return ms, kb(status)

    def documents(self) -> tuple[float, float]:
        """The texts of the set: ms and KB."""
        with self._session_factory() as session:
            use_case = self._container.get_review_documents_use_case(session)

            def read() -> str:
                texts = use_case.execute(self.scope)
                return json.dumps([d.model_dump(mode="json") for d in texts])

            body, ms = timed(read)
        return ms, len(body) / BYTES_PER_KB

    def run_generation(self, kind: GenerationKind) -> tuple[int, float]:
        """A ✨ run of the kind for the set's cards nothing was made for: queued, ms."""
        with self._session_factory() as session:
            use_case = self._container.run_generation_use_case(session)
            return timed(lambda: use_case.execute(self.scope, kind, GenerationScope.MISSING))

    def add_word(self, source_id: int) -> int | None:
        """A word added from the chapter's text, as another tab adds it: the phrase id of
        its card, or None when no line of the first ADD_TRIES takes one."""
        with self._session_factory() as session:
            document = SqlaDocumentRepository(session).get(source_id)
            use_case = self._container.add_manual_candidate_use_case(session)
            lines = [
                (block_index, line_index, line.text)
                for block_index, block in enumerate(document.blocks if document else ())
                if isinstance(block, Paragraph)
                for line_index, line in enumerate(block.lines)
                if len(line.text.split()) > 1
            ]
            for block_index, line_index, text in lines[:ADD_TRIES]:
                selection = SelectionDTO(
                    start_block=block_index, start_line=line_index, start_char=0,
                    end_block=block_index, end_line=line_index, end_char=len(text),
                )
                try:
                    return use_case.execute(source_id, [1], selection).phrase_id
                except DomainError:
                    continue
        return None

    def recut(self, source_id: int) -> tuple[dict[str, int], float]:
        """The chapter cut again: what it changed, ms."""
        with self._session_factory() as session:
            use_case = self._container.rebuild_source_use_case(session)
            done, ms = timed(lambda: use_case.execute(source_id, RebuildMode.RECUT))
        return done.counts.model_dump(), ms


def _serialised[M: BaseModel](answer: M) -> M:
    """The answer as the route sends it: serialised, so its cost is counted."""
    answer.model_dump_json()
    return answer


def _context(answer: ReviewUpdateDTO, current: int | None = None) -> ReviewContext:
    return ReviewContext(review_id=answer.review_id, since=answer.revision, current=current)


def measure_open(bench: ReviewBench) -> tuple[dict[str, object], ReviewUpdateDTO]:
    opened: dict[str, object] = {}
    relevance: ReviewUpdateDTO | None = None
    for sort in CandidateSortOrder:
        answer, ms, size = bench.open(sort)
        assert answer.layout is not None
        opened[sort.value] = {
            "ms": ms, "json_kb": size,
            "total_rows": answer.layout.total_rows, "total_cards": answer.layout.total_cards,
            "rows_sent": len(answer.layout.rows), "cards_sent": len(answer.cards),
        }
        if sort is CandidateSortOrder.RELEVANCE:
            relevance = answer
    assert relevance is not None
    return opened, relevance


def measure_windows(
    bench: ReviewBench, opened: ReviewUpdateDTO, rng: random.Random,
) -> dict[str, object]:
    assert opened.layout is not None
    ctx = _context(opened)
    timings: list[float] = []
    sizes: list[float] = []
    for _ in range(WINDOWS):
        start = rng.randrange(max(1, opened.layout.total_rows - WINDOW_ROWS))
        answer, ms = bench.rows(ctx, start, WINDOW_ROWS)
        timings.append(ms)
        sizes.append(kb(answer))
    return {"raw": timings, **summary(timings), "json_kb_median": statistics.median(sizes)}


def measure_presses(
    bench: ReviewBench, open_ids: list[int], presses: int,
) -> dict[str, object]:
    """Presses on a review that served SERVED_ROWS rows, each brought up to date."""
    opened, _, _ = bench.open(CandidateSortOrder.RELEVANCE)
    served, _ = bench.rows(_context(opened), 0, SERVED_ROWS)
    since = served.revision
    decide_ms: list[float] = []
    update_ms: list[float] = []
    sizes: list[float] = []
    refused = 0
    for phrase_id in open_ids:
        if len(decide_ms) >= presses:
            break
        button = PRESS_BUTTONS[len(decide_ms) % len(PRESS_BUTTONS)]
        ctx = ReviewContext(review_id=opened.review_id, since=since, current=phrase_id)
        pressed = bench.press(ctx, phrase_id, button)
        if pressed is None:
            refused += 1
            continue
        answer, decided, updated = pressed
        decide_ms.append(decided)
        update_ms.append(updated)
        sizes.append(kb(answer))
        since = answer.revision
    return {
        "presses": len(decide_ms),
        "refused_presses": refused,
        "served_rows": SERVED_ROWS,
        "press_decide_ms": {"raw": decide_ms, **summary(decide_ms)},
        "press_update_ms": {"raw": update_ms, **summary(update_ms)},
        "press_json_kb": summary(sizes),
    }


def measure_heaviest_lemma(
    bench: ReviewBench, rows: Rows, collection_id: int,
) -> dict[str, object]:
    lemma, cards = rows.all(HEAVIEST_LEMMA_SQL, collection_id)[0]
    [phrase_id] = rows.ints(OPEN_CARD_OF_LEMMA_SQL, collection_id, lemma)
    opened, _, _ = bench.open(CandidateSortOrder.RELEVANCE)
    served, _ = bench.rows(_context(opened), 0, SERVED_ROWS)
    pressed = bench.press(_context(served, phrase_id), phrase_id, Press.KNOWN)
    if pressed is None:
        return {"lemma": lemma, "cards": cards, "refused": True}
    answer, decided, updated = pressed
    return {
        "lemma": lemma, "cards": cards, "decide_ms": decided, "update_ms": updated,
        "json_kb": kb(answer), "cards_sent": len(answer.cards), "done_sent": len(answer.done),
    }


def measure_recut(
    bench: ReviewBench, rows: Rows, source_ids: list[int],
) -> dict[str, object]:
    """A chapter in the middle of the book cut again while a review is open, then the poll
    that places its new cards."""
    source_id = source_ids[len(source_ids) // 2]
    opened, _, _ = bench.open(CandidateSortOrder.RELEVANCE)
    served, _ = bench.rows(_context(opened), 0, SERVED_ROWS)
    try:
        counts, recut_ms = bench.recut(source_id)
    except DomainError as e:
        return {"source_id": source_id, "error": repr(e)}
    answer, changes_ms = bench.changes(_context(served))
    return {
        "source_id": source_id, "recut_s": recut_ms / MS, "counts": counts,
        "changes_ms": changes_ms, "changes_json_kb": kb(answer),
        "cards_sent": len(answer.cards), "removed_sent": len(answer.removed),
        "done_sent": len(answer.done),
        "replace": answer.layout.replace if answer.layout is not None else None,
    }


def measure_new_card(bench: ReviewBench, source_ids: list[int]) -> dict[str, object]:
    """A word added in a chapter from another tab, then the poll of an open review that
    places its new card into the held order."""
    source_id = source_ids[len(source_ids) // 2]
    opened, _, _ = bench.open(CandidateSortOrder.RELEVANCE)
    served, _ = bench.rows(_context(opened), 0, SERVED_ROWS)
    phrase_id = bench.add_word(source_id)
    if phrase_id is None:
        return {"source_id": source_id, "error": "no line took a word"}
    answer, changes_ms = bench.changes(_context(served))
    return {
        "source_id": source_id, "phrase_id": phrase_id, "changes_ms": changes_ms,
        "changes_json_kb": kb(answer), "cards_sent": len(answer.cards),
        "done_sent": len(answer.done),
        "replace": answer.layout.replace if answer.layout is not None else None,
    }


def run(args: BenchArgs) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        copy = copy_to_temp(args.db, Path(directory))
        rows = Rows(copy)
        collections = rows.ints(COLLECTION_ID_SQL, args.collection)
        if not collections:
            raise SystemExit(f"No collection named {args.collection!r}")
        collection_id = collections[0]
        bench = ReviewBench(copy, collection_id)
        result: dict[str, object] = {"db": str(args.db), "collection": args.collection,
                                     "seed": args.seed, **bench.start()}
        rng = random.Random(args.seed)
        opened, relevance = measure_open(bench)
        result["open"] = opened
        in_text_order = opened[CandidateSortOrder.CHRONOLOGICAL.value]
        assert isinstance(in_text_order, dict)
        result["cards"] = in_text_order["total_cards"]
        result["rows_ms"] = measure_windows(bench, relevance, rng)
        source_ids = rows.ints(SOURCES_SQL, collection_id)
        [last_card] = rows.ints(CARD_OF_SOURCE_SQL, source_ids[-1])
        around, around_ms = bench.around(_context(relevance), last_card)
        result["around_last_chapter"] = {"ms": around_ms, "json_kb": kb(around)}
        status_ms, status_kb = bench.generation_status()
        result["generation_status"] = {"ms": status_ms, "json_kb": status_kb}
        documents_ms, documents_kb = bench.documents()
        result["documents"] = {"ms": documents_ms, "json_kb": documents_kb}
        result["heaviest_lemma"] = measure_heaviest_lemma(bench, rows, collection_id)
        open_ids = rows.ints(OPEN_CARDS_SQL, collection_id)
        rng.shuffle(open_ids)
        result |= measure_presses(bench, open_ids, args.presses)
        runs: dict[str, object] = {}
        for kind in RUN_KINDS:
            bench.writes.held_ms.clear()
            queued, ms = bench.run_generation(kind)
            runs[kind.value] = {
                "queued": queued, "s": ms / MS, "writes": len(bench.writes.held_ms),
                "longest_write_ms": max(bench.writes.held_ms, default=0.0),
            }
        result["generation_run"] = runs
        queued_ms, queued_kb = bench.generation_status()
        result["generation_status_queued"] = {
            "ms": queued_ms, "json_kb": queued_kb, "jobs": rows.ints(JOBS_SQL)[0],
        }
        result["startup_rebuild_queued_s"] = bench.rebuild() / MS
        result["recut_chapter"] = measure_recut(bench, rows, source_ids)
        result["new_card_poll"] = measure_new_card(bench, source_ids)
    return result


def print_table(result: dict[str, object]) -> None:
    print(json.dumps(
        {k: v for k, v in result.items() if k not in ("rows_ms", "press_decide_ms",
                                                    "press_update_ms")},
        indent=2,
    ))
    print(f"{'part':<16}{'median':>10}{'p95':>10}{'p99':>10}{'max':>10}  (ms)")
    for key in ("rows_ms", "press_decide_ms", "press_update_ms"):
        part = result[key]
        assert isinstance(part, dict)
        if part.get("median") is not None:
            print(f"{key[:-3]:<16}{part['median']:>10.1f}{part['p95']:>10.1f}"
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
