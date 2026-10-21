"""Build a benchmark database: a copy of the app database plus a big real book (Worm) split
into chapter sources and processed, so the review has book-sized data to be measured on.

Run it with `make bench-db`. It works on a copy only; the source database is never changed.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from backend.application.dto.add_source_dtos import SourcesCreated
from backend.application.source_intake.naming import Naming
from backend.application.source_intake.typed_input import typed_inputs
from backend.domain.value_objects.collection_choice import CollectionChoice
from backend.domain.value_objects.naming_rule import DEFAULT_NAMING_RULE, NamingRule
from backend.domain.value_objects.question import Answers
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import create_session_factory, open_query_only

COLLECTION_NAME = "Worm"
SPLIT_QUESTION = "book.split"
SPLIT_ANSWER = "split"
ALL_CHAPTERS = 0
CARDS_SQL = (
    "SELECT COUNT(*) FROM phrases p JOIN candidates c ON c.id = p.candidate_id "
    "JOIN sources s ON s.id = c.source_id "
    "WHERE s.collection_id = ? AND p.shown_by IS NOT NULL"
)


@dataclass(frozen=True)
class BuildArgs:
    source_db: Path
    epub: Path
    chapters: int
    out: Path


def parse_args(argv: list[str] | None = None) -> BuildArgs:
    default_db = Path(os.getenv("DATA_DIR", "./data")) / "app.db"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", type=Path, default=default_db)
    parser.add_argument("--epub", type=Path, required=True)
    parser.add_argument("--chapters", type=int, default=ALL_CHAPTERS, help="0 = all")
    parser.add_argument("--out", type=Path, required=True)
    ns = parser.parse_args(argv)
    return BuildArgs(ns.source_db, ns.epub, ns.chapters, ns.out)


def backup_copy(source: Path, target: Path) -> None:
    """The online backup API, so the copy is consistent even if the source is in use."""
    origin = open_query_only(str(source))
    copy = sqlite3.connect(target)
    try:
        origin.backup(copy)
    finally:
        copy.close()
        origin.close()


def clear_collection(container: Container, db_url: str, name: str) -> None:
    """The source database may hold an earlier copy of the book: the benchmark collection
    must hold only the chapters built now, so the old one goes first."""
    connection = sqlite3.connect(db_url.removeprefix("sqlite:///"))
    try:
        collection_ids = [
            row[0]
            for row in connection.execute(
                "SELECT id FROM collections WHERE name = ? AND deleted_at IS NULL", (name,),
            )
        ]
        source_ids = [
            row[0]
            for collection_id in collection_ids
            for row in connection.execute(
                "SELECT id FROM sources WHERE collection_id = ?", (collection_id,),
            )
        ]
    finally:
        connection.close()
    if not collection_ids:
        return
    with create_session_factory(db_url)() as session:
        container.delete_sources_use_case(session).execute(source_ids)
        for collection_id in collection_ids:
            container.delete_collection_use_case(session).execute(collection_id)
        session.commit()
    print(f"removed the earlier {name!r}: {len(source_ids)} sources")


def add_book(container: Container, db_url: str, epub: Path) -> SourcesCreated:
    session_factory = create_session_factory(db_url)
    with session_factory() as session:
        result = container.add_source_use_case(session).execute(
            typed_inputs(str(epub)),
            None,
            [Answers({SPLIT_QUESTION: SPLIT_ANSWER})],
            Naming(CollectionChoice(new_name=COLLECTION_NAME), NamingRule(DEFAULT_NAMING_RULE)),
        )
        session.commit()
    if not isinstance(result, SourcesCreated):
        raise SystemExit(f"Adding the book did not create sources: {result!r}")
    return result


def process_chapters(container: Container, db_url: str, source_ids: list[int]) -> None:
    session_factory = create_session_factory(db_url)
    total = len(source_ids)
    began = time.perf_counter()
    for number, source_id in enumerate(source_ids, 1):
        chapter_began = time.perf_counter()
        with session_factory() as session:
            use_case = container.process_source_use_case(session)
            use_case.start(source_id)
            session.commit()
            use_case.execute(source_id)
            session.commit()
        print(
            f"chapter {number}/{total} source {source_id} "
            f"{time.perf_counter() - chapter_began:.1f}s "
            f"(total {time.perf_counter() - began:.0f}s)",
            flush=True,
        )


def count_cards(db_path: Path, collection_id: int) -> int:
    connection = sqlite3.connect(db_path)
    try:
        return int(connection.execute(CARDS_SQL, (collection_id,)).fetchone()[0])
    finally:
        connection.close()


def main() -> int:
    args = parse_args()
    if args.out.exists():
        print(f"Refusing to overwrite {args.out}", file=sys.stderr)
        return 1
    if not args.source_db.is_file() or not args.epub.is_file():
        print("--source-db and --epub must be existing files", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    backup_copy(args.source_db, args.out)
    db_url = f"sqlite:///{args.out.resolve()}"
    container = Container(session_factory=create_session_factory(db_url))
    clear_collection(container, db_url, COLLECTION_NAME)
    created = add_book(container, db_url, args.epub)
    if created.collection_id is None:
        raise SystemExit("The book was not gathered into a collection")
    chosen = created.source_ids if args.chapters == ALL_CHAPTERS else (
        created.source_ids[: args.chapters]
    )
    print(f"book split into {len(created.source_ids)} chapters; processing {len(chosen)}")
    process_chapters(container, db_url, chosen)
    cards = count_cards(args.out, created.collection_id)
    print(f"cards in collection {COLLECTION_NAME!r}: {cards}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
