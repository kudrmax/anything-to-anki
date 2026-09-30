"""Deleting candidates must not leave their enrichment behind.

Enrichment rows are keyed by candidate id. If they survive the candidate,
a later candidate that gets the same id inherits someone else's meaning,
screenshot, pronunciation or "already synced to Anki" mark.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from sqlalchemy import text

from tests.integration.conftest import insert_source

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SOURCE_ID = 1
ENRICHMENT_TABLES = (
    "candidate_meanings",
    "candidate_media",
    "candidate_pronunciations",
    "candidate_tts",
    "anki_synced_cards",
)


def _create_candidate(repo: SqlaCandidateRepository, lemma: str) -> int:
    created = repo.create_batch([
        StoredCandidate(
            source_id=SOURCE_ID,
            lemma=lemma,
            pos="NOUN",
            cefr_level=None,
            zipf_frequency=4.0,
            context_fragment=f"a {lemma}",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
        )
    ])[0]
    assert created.id is not None
    return created.id


def _enrich(session: Session, candidate_id: int) -> None:
    params = {"cid": candidate_id}
    session.execute(
        text("INSERT INTO candidate_meanings (candidate_id, meaning) VALUES (:cid, 'm')"),
        params,
    )
    session.execute(
        text("INSERT INTO candidate_media (candidate_id, screenshot_path) VALUES (:cid, 's')"),
        params,
    )
    session.execute(
        text(
            "INSERT INTO candidate_pronunciations (candidate_id, us_audio_path)"
            " VALUES (:cid, 'p')"
        ),
        params,
    )
    session.execute(
        text("INSERT INTO candidate_tts (candidate_id, audio_path) VALUES (:cid, 't')"),
        params,
    )
    session.execute(
        text("INSERT INTO anki_synced_cards (candidate_id, anki_note_id) VALUES (:cid, 1)"),
        params,
    )


def _rows_for(session: Session, table: str, candidate_id: int) -> int:
    count: int = session.execute(
        text(f"SELECT COUNT(*) FROM {table} WHERE candidate_id = :cid"),
        {"cid": candidate_id},
    ).scalar_one()
    return count


def test_deleting_candidates_removes_their_enrichment(db_session: Session) -> None:
    insert_source(db_session, SOURCE_ID)
    repo = SqlaCandidateRepository(db_session)
    candidate_id = _create_candidate(repo, "advance")
    _enrich(db_session, candidate_id)

    repo.delete_by_source(SOURCE_ID)

    for table in ENRICHMENT_TABLES:
        assert _rows_for(db_session, table, candidate_id) == 0, table


def test_candidate_ids_are_never_reused(db_session: Session) -> None:
    insert_source(db_session, SOURCE_ID)
    repo = SqlaCandidateRepository(db_session)
    deleted_id = _create_candidate(repo, "advance")
    repo.delete_by_source(SOURCE_ID)

    new_id = _create_candidate(repo, "instant")

    assert new_id > deleted_id
