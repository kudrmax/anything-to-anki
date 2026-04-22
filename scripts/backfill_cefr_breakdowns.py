"""Backfill missing cefr_breakdowns rows for candidates that predate migration 0013.

Usage (from project root):
    make backfill-breakdowns            # run on local data/app.db
    make backfill-breakdowns DRY_RUN=1  # dry run, no writes

Runs inside the app Docker container where all Python deps are available.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cambridge.cefr_source import CambridgeCEFRSource
from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.efllex_cefr_source import EFLLexCEFRSource
from backend.infrastructure.adapters.kelly_cefr_source import KellyCEFRSource
from backend.infrastructure.adapters.oxford_cefr_source import OxfordCEFRSource


def _build_classifier(dictionaries_dir: Path) -> VotingCEFRClassifier:
    cefr_dir = dictionaries_dir / "cefr"
    oxford = OxfordCEFRSource(cefr_dir / "oxford5000.csv")
    cambridge = CambridgeCEFRSource(
        CambridgeSQLiteReader(dictionaries_dir / "cambridge.db"),
    )
    sources = [
        CefrpyCEFRSource(),
        EFLLexCEFRSource(cefr_dir / "efllex.tsv"),
        KellyCEFRSource(cefr_dir / "kelly.csv"),
    ]
    return VotingCEFRClassifier(sources, priority_sources=[oxford, cambridge])


def _level_to_str(level: CEFRLevel) -> str | None:
    if level is CEFRLevel.UNKNOWN:
        return None
    return level.name


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill missing cefr_breakdowns rows")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done, don't write")
    args = parser.parse_args()

    # In Docker: DATA_DIR=/data, dictionaries at /app/dictionaries
    # Locally with venv: DATA_DIR=data (or .), dictionaries at ./dictionaries
    data_dir = os.getenv("DATA_DIR", "data")
    db_path = Path(data_dir) / "app.db"
    if not db_path.exists():
        print(f"Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    dictionaries_dir = Path("/app/dictionaries")
    if not dictionaries_dir.exists():
        dictionaries_dir = Path("dictionaries")
    if not dictionaries_dir.exists():
        print(f"Dictionaries not found", file=sys.stderr)
        sys.exit(1)

    print(f"DB: {db_path}")
    print(f"Dictionaries: {dictionaries_dir}")
    print("Loading CEFR sources...")
    classifier = _build_classifier(dictionaries_dir)

    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    orphans = conn.execute(
        """
        SELECT c.id, c.lemma, c.pos
        FROM candidates c
        LEFT JOIN cefr_breakdowns b ON b.candidate_id = c.id
        WHERE b.id IS NULL
        """,
    ).fetchall()

    print(f"Candidates without breakdown: {len(orphans)}")

    if not orphans:
        print("Nothing to do.")
        conn.close()
        return

    if args.dry_run:
        for cid, lemma, pos in orphans[:10]:
            bd = classifier.classify_detailed(lemma, pos)
            print(f"  [{cid}] {lemma}/{pos} -> {bd.final_level.name} ({bd.decision_method})")
        if len(orphans) > 10:
            print(f"  ... and {len(orphans) - 10} more")
        print("Dry run — no changes written.")
        conn.close()
        return

    inserted = 0
    for cid, lemma, pos in orphans:
        bd = classifier.classify_detailed(lemma, pos)

        cambridge: str | None = None
        cefrpy: str | None = None
        efllex_distribution: str | None = None
        oxford: str | None = None
        kelly: str | None = None

        for vote in [*bd.priority_votes, *bd.votes]:
            level_str = _level_to_str(vote.top_level)
            if vote.source_name == "Cambridge Dictionary":
                cambridge = level_str
            elif vote.source_name == "CEFRpy":
                cefrpy = level_str
            elif vote.source_name == "EFLLex":
                dist = {
                    lvl.name: round(prob, 4)
                    for lvl, prob in vote.distribution.items()
                    if lvl is not CEFRLevel.UNKNOWN and prob > 0
                }
                efllex_distribution = json.dumps(dist) if dist else None
            elif vote.source_name == "Oxford 5000":
                oxford = level_str
            elif vote.source_name == "Kelly List":
                kelly = level_str

        conn.execute(
            """
            INSERT INTO cefr_breakdowns
                (candidate_id, decision_method, cambridge, cefrpy, efllex_distribution, oxford, kelly)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (cid, bd.decision_method, cambridge, cefrpy, efllex_distribution, oxford, kelly),
        )
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Done. Inserted {inserted} breakdown rows.")


if __name__ == "__main__":
    main()
