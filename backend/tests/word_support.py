"""Words and their phrases straight in the database, for tests below the repositories."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.models import dump_phrase
from sqlalchemy import text

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection
    from sqlalchemy.orm import Session

CREATED_AT = "2026-01-01 00:00:00"


def insert_word(
    db: Session | Connection,
    word_id: int,
    *,
    source_id: int = 1,
    lemma: str | None = None,
    status: str = CandidateStatus.PENDING.value,
    phrase_text: str | None = None,
    pos: str = "NOUN",
    zipf_frequency: float = 3.0,
    is_sweet_spot: bool = False,
) -> None:
    """A word with one shown phrase whose id is the word's id.

    The lemma is `word<id>` unless given: lemmas of a source are unique. `status` may be
    "skip": the word is pending and its phrase is skipped.
    """
    lemma = lemma or f"word{word_id}"
    skipped = status == CandidateStatus.SKIP.value
    db.execute(
        text(
            "INSERT INTO candidates (id, source_id, lemma, pos, zipf_frequency, is_sweet_spot,"
            " occurrences, status, is_phrasal_verb)"
            " VALUES (:id, :source_id, :lemma, :pos, :zipf, :sweet, 1, :status, 0)"
        ),
        {
            "id": word_id, "source_id": source_id, "lemma": lemma, "pos": pos,
            "zipf": zipf_frequency, "sweet": is_sweet_spot,
            "status": CandidateStatus.PENDING.value if skipped else status,
        },
    )
    is_decision = status in (CandidateStatus.LEARN.value, CandidateStatus.KNOWN.value)
    db.execute(
        text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, skipped,"
            " is_decision, decision_kind, created_at)"
            " VALUES (:id, :id, :phrase, 'auto', 'selection', :skipped, :decision, :kind,"
            " :created_at)"
        ),
        {
            "id": word_id,
            "phrase": dump_phrase(phrase(phrase_text or lemma, lemma)),
            "skipped": skipped,
            "decision": is_decision,
            "kind": "learn" if is_decision else None,
            "created_at": CREATED_AT,
        },
    )
