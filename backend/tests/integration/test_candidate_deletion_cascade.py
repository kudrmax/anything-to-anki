"""Deleting candidates must not leave their enrichment behind.

Enrichment rows are keyed by candidate id. If they survive the candidate,
a later candidate that gets the same id inherits someone else's meaning,
screenshot, pronunciation or "already synced to Anki" mark.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from sqlalchemy import text

from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.word_support import SeedWord, store_cards

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

SOURCE_ID = 1
WORD_TABLES = ("candidate_pronunciations", "anki_synced_cards", "phrases")
PHRASE_TABLES = ("candidate_meanings", "candidate_media", "candidate_tts", "phrase_words")


def _create_candidate(repo: SqlaCandidateRepository, lemma: str) -> int:
    created = store_cards(repo._session, [
        SeedWord(
            source_id=SOURCE_ID,
            lemma=lemma,
            pos="NOUN",
            cefr_level=None,
            zipf_frequency=4.0,
            source_phrase=phrase(f"a {lemma}", lemma),
            occurrences=1,
            status=WordStatus.PENDING,
        )
    ])[0]
    assert created.id is not None
    return created.id


def _phrase_of(session: Session, candidate_id: int) -> int:
    phrase_id: int = session.execute(
        text("SELECT id FROM phrases WHERE candidate_id = :cid"), {"cid": candidate_id},
    ).scalar_one()
    return phrase_id


def _enrich(session: Session, candidate_id: int, phrase_id: int) -> None:
    params = {"cid": candidate_id, "pid": phrase_id}
    session.execute(
        text("INSERT INTO candidate_meanings (phrase_id, meaning) VALUES (:pid, 'm')"),
        params,
    )
    session.execute(
        text("INSERT INTO candidate_media (phrase_id, screenshot_path) VALUES (:pid, 's')"),
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
        text("INSERT INTO candidate_tts (phrase_id, audio_path) VALUES (:pid, 't')"),
        params,
    )
    session.execute(
        text(
            "INSERT INTO anki_synced_cards (candidate_id, phrase_id, anki_note_id)"
            " VALUES (:cid, :pid, 1)"
        ),
        params,
    )


def _rows_for(session: Session, table: str, column: str, row_id: int) -> int:
    count: int = session.execute(
        text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :id"),  # noqa: S608
        {"id": row_id},
    ).scalar_one()
    return count


def test_deleting_candidates_removes_their_enrichment(db_session: Session) -> None:
    insert_source(db_session, SOURCE_ID)
    repo = SqlaCandidateRepository(db_session)
    candidate_id = _create_candidate(repo, "advance")
    phrase_id = _phrase_of(db_session, candidate_id)
    _enrich(db_session, candidate_id, phrase_id)

    repo.delete_by_source(SOURCE_ID)

    for table in WORD_TABLES:
        assert _rows_for(db_session, table, "candidate_id", candidate_id) == 0, table
    for table in PHRASE_TABLES:
        assert _rows_for(db_session, table, "phrase_id", phrase_id) == 0, table


def test_candidate_ids_are_never_reused(db_session: Session) -> None:
    insert_source(db_session, SOURCE_ID)
    repo = SqlaCandidateRepository(db_session)
    deleted_id = _create_candidate(repo, "advance")
    repo.delete_by_source(SOURCE_ID)

    new_id = _create_candidate(repo, "instant")

    assert new_id > deleted_id
