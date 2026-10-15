"""Media of a merged word keep the old card id in their names; the DB still points at them."""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.adapters.local_media_files import DRAFT_MARKER
from backend.infrastructure.persistence.database import (
    create_session_factory,
    reconcile_media_files,
)
from backend.infrastructure.persistence.models import (
    Base,
    CandidateMediaModel,
    CandidateTTSModel,
)
from backend.infrastructure.services.lazy_media_reconciler import LazyMediaReconciler
from sqlalchemy import select, text

from tests.integration.conftest import insert_source
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

SOURCE = 1
WORD = 10
PHRASE = phrase_id_of(WORD)
MERGED_CARD = 7
ORPHAN_CARD = 99


def test_a_file_the_db_points_at_survives_without_its_card(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    bind = factory.kw["bind"]
    Base.metadata.create_all(bind)
    media_dir = tmp_path / "media" / str(SOURCE)
    media_dir.mkdir(parents=True)
    merged = media_dir / f"{MERGED_CARD}_screenshot.webp"
    orphan = media_dir / f"{ORPHAN_CARD}_screenshot.webp"
    merged.write_bytes(b"keep")
    orphan.write_bytes(b"orphan")
    with factory() as session:
        insert_source(session, SOURCE)
        insert_word(session, WORD, source_id=SOURCE)
        session.add(CandidateMediaModel(phrase_id=PHRASE, screenshot_path=str(merged)))
        session.commit()

    reconcile_media_files(factory, str(tmp_path / "media"))

    assert merged.exists()
    assert not orphan.exists()


GONE_PHRASE = 98
OTHER_PHRASE = PHRASE + 1


def test_files_of_phrases_follow_the_paths_the_db_points_at(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(factory.kw["bind"])
    media_dir = tmp_path / "media" / str(SOURCE)
    media_dir.mkdir(parents=True)
    made = media_dir / f"p{PHRASE}_screenshot.webp"
    being_made = media_dir / f"p{PHRASE}_audio.m4a"
    of_gone_phrase = media_dir / f"p{GONE_PHRASE}_screenshot.webp"
    old_clip_spoken = media_dir / f"{MERGED_CARD}_audio.m4a"
    for path in (made, being_made, of_gone_phrase, old_clip_spoken):
        path.write_bytes(b"x")
    with factory() as session:
        insert_source(session, SOURCE)
        insert_word(session, WORD, source_id=SOURCE)
        session.add(CandidateMediaModel(phrase_id=PHRASE, screenshot_path=str(made)))
        session.add(CandidateTTSModel(phrase_id=PHRASE, audio_path=str(old_clip_spoken)))
        session.commit()

    reconcile_media_files(factory, str(tmp_path / "media"))

    assert made.exists()
    assert being_made.exists()  # its phrase is still there: the worker may be writing it
    assert old_clip_spoken.exists()  # the speech row points at it
    assert not of_gone_phrase.exists()


def test_speech_nobody_points_at_is_reclaimed(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(factory.kw["bind"])
    media_dir = tmp_path / "media" / str(SOURCE)
    media_dir.mkdir(parents=True)
    spoken = media_dir / f"p{PHRASE}_tts.m4a"
    of_gone_phrase = media_dir / f"p{GONE_PHRASE}_tts.m4a"
    of_gone_card = media_dir / f"{ORPHAN_CARD}_tts.m4a"
    for path in (spoken, of_gone_phrase, of_gone_card):
        path.write_bytes(b"x")
    with factory() as session:
        insert_source(session, SOURCE)
        insert_word(session, WORD, source_id=SOURCE)
        session.add(CandidateTTSModel(phrase_id=PHRASE, audio_path=str(spoken)))
        session.commit()

    reconcile_media_files(factory, str(tmp_path / "media"))

    assert spoken.exists()
    assert not of_gone_phrase.exists()
    assert not of_gone_card.exists()


@pytest.mark.asyncio
async def test_a_missing_file_clears_only_the_rows_pointing_at_it(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(factory.kw["bind"])
    media_dir = tmp_path / "media" / str(SOURCE)
    media_dir.mkdir(parents=True)
    gone = media_dir / f"p{OTHER_PHRASE}_screenshot.webp"
    kept = media_dir / f"p{PHRASE}_screenshot.webp"
    kept.write_bytes(b"x")
    with factory() as session:
        insert_source(session, SOURCE)
        insert_word(session, WORD, source_id=SOURCE)
        session.execute(text(
            "INSERT INTO phrases (id, candidate_id, source_phrase, origin, shown_by, skipped,"
            " is_decision, created_at)"
            " SELECT :id, candidate_id, source_phrase, 'manual', 'user', 0, 0, created_at"
            " FROM phrases WHERE id = :phrase"
        ), {"id": OTHER_PHRASE, "phrase": PHRASE})
        session.add(CandidateMediaModel(
            phrase_id=PHRASE, screenshot_path=str(kept), audio_path=str(gone),
        ))
        session.add(CandidateMediaModel(phrase_id=OTHER_PHRASE, screenshot_path=str(gone)))
        session.commit()

    await LazyMediaReconciler(factory, str(tmp_path / "media")).schedule(SOURCE, gone.name)
    await asyncio.sleep(0.2)

    with factory() as session:
        rows = {
            row.phrase_id: (row.screenshot_path, row.audio_path)
            for row in session.scalars(select(CandidateMediaModel))
        }
    assert rows == {PHRASE: (str(kept), None), OTHER_PHRASE: (None, None)}


def test_drafts_left_by_a_crash_are_dropped_at_startup(tmp_path: Path) -> None:
    factory = create_session_factory(f"sqlite:///{tmp_path / 'app.db'}")
    Base.metadata.create_all(factory.kw["bind"])
    media_dir = tmp_path / "media" / str(SOURCE)
    media_dir.mkdir(parents=True)
    made = media_dir / f"p{PHRASE}_tts.m4a"
    drafts = [
        media_dir / f"p{PHRASE}_tts{DRAFT_MARKER}1a2b3c4d.m4a",
        media_dir / f"p{PHRASE}_screenshot{DRAFT_MARKER}5e6f7a8b.webp",
    ]
    users_file = media_dir / "notes.part-of-my-list.txt"
    for path in (made, *drafts, users_file):
        path.write_bytes(b"x")
    with factory() as session:
        insert_source(session, SOURCE)
        insert_word(session, WORD, source_id=SOURCE)
        session.add(CandidateTTSModel(phrase_id=PHRASE, audio_path=str(made)))
        session.commit()

    reconcile_media_files(factory, str(tmp_path / "media"))

    assert sorted(p.name for p in media_dir.iterdir()) == sorted([made.name, users_file.name])
