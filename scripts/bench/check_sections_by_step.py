"""Compare `sections_by_step` with `card_section` for every card of a database, at every step.

Run it with `.venv/bin/python -m scripts.bench.check_sections_by_step --db bench.db`. The input
database is never modified: the check reads a throwaway copy in the system temp directory.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

from backend.application.utils.review_cards import ReviewCards
from backend.domain.services.candidate_sections import card_section, sections_by_step
from backend.domain.value_objects.frequent_word_threshold import (
    THRESHOLD_STEPS,
    FrequentWordThreshold,
)
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.infrastructure.container import Container
from backend.infrastructure.persistence.database import create_session_factory
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_word_state_repository import (
    SqlaWordStateRepository,
)
from sqlalchemy import text

from scripts.bench.bench_review import copy_to_temp

STEP_KEY = "step"
MAX_SHOWN_MISMATCHES = 5


def parse_args(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    return Path(parser.parse_args(argv).db)


def check(db: Path) -> int:
    """Prints the cards checked and the mismatches; returns the number of mismatches."""
    session_factory = create_session_factory(f"sqlite:///{db}")
    container = Container(session_factory=session_factory)
    with session_factory() as session:
        recorder = container._change_recorder(session)  # noqa: SLF001 — a one-off check
        review_cards = ReviewCards(
            SqlaCandidateRepository(session, recorder),
            SqlaOccurrenceRepository(session, recorder),
            SqlaWordStateRepository(session, recorder),
            container._user_vocabulary(session),  # noqa: SLF001
        )
        knowledge = container._user_knowledge(session).current()  # noqa: SLF001
        source_ids = [row[0] for row in session.execute(text("SELECT id FROM sources"))]
        cards = review_cards.of_sources(source_ids)
        began = time.perf_counter()
        mismatches = []
        for card in cards:
            by_step = sections_by_step(card, knowledge.base)
            expected = tuple(
                card_section(
                    card,
                    UserKnowledge(knowledge.vocabulary, knowledge.user_level, step),
                    FrequentWordThreshold(STEP_KEY, step, ()),
                )
                for step in THRESHOLD_STEPS
            )
            if by_step != expected:
                mismatches.append((card.phrase_id, by_step, expected))
        elapsed = time.perf_counter() - began
    print(f"cards={len(cards)} steps={len(THRESHOLD_STEPS)} mismatches={len(mismatches)} "
          f"check={elapsed:.1f}s")
    for phrase_id, got, want in mismatches[:MAX_SHOWN_MISMATCHES]:
        print(f"  phrase {phrase_id}: by step {[s.value for s in got]} "
              f"!= card_section {[s.value for s in want]}")
    return len(mismatches)


def main() -> int:
    db = parse_args()
    with tempfile.TemporaryDirectory() as directory:
        mismatches = check(copy_to_temp(db, Path(directory)))
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
