"""Media of a merged word keep the old card id in their names; the DB still points at them."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.persistence.database import (
    create_session_factory,
    reconcile_media_files,
)
from backend.infrastructure.persistence.models import Base, CandidateMediaModel

from tests.integration.conftest import insert_source
from tests.word_support import insert_word

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

SOURCE = 1
WORD = 10
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
        session.add(CandidateMediaModel(phrase_id=WORD, screenshot_path=str(merged)))
        session.commit()

    reconcile_media_files(factory, str(tmp_path / "media"))

    assert merged.exists()
    assert not orphan.exists()
