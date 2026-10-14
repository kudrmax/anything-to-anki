"""Media files of phrases are made under a draft name and put in place only when kept."""
from __future__ import annotations

from pathlib import Path

import pytest
from backend.infrastructure.adapters.local_media_files import LocalMediaFiles

pytestmark = pytest.mark.unit


def test_a_draft_keeps_the_extension_and_waits_beside_the_final_file(tmp_path: Path) -> None:
    draft = LocalMediaFiles(str(tmp_path)).draft(3, 17, "tts.m4a")

    assert draft.final_path == str(tmp_path / "3" / "p17_tts.m4a")
    assert Path(draft.path).parent == tmp_path / "3"
    assert draft.path != draft.final_path
    assert draft.path.endswith(".m4a")


def test_keeping_puts_the_draft_in_place_of_the_old_file(tmp_path: Path) -> None:
    files = LocalMediaFiles(str(tmp_path))
    draft = files.draft(3, 17, "tts.m4a")
    Path(draft.final_path).write_bytes(b"old")
    Path(draft.path).write_bytes(b"new")

    files.keep(draft)
    files.discard(draft)

    assert Path(draft.final_path).read_bytes() == b"new"
    assert [p.name for p in (tmp_path / "3").iterdir()] == ["p17_tts.m4a"]


def test_discarding_drops_the_draft_and_leaves_the_old_file(tmp_path: Path) -> None:
    files = LocalMediaFiles(str(tmp_path))
    draft = files.draft(3, 17, "screenshot.webp")
    Path(draft.final_path).write_bytes(b"old")
    Path(draft.path).write_bytes(b"stale")

    files.discard(draft)

    assert [p.name for p in (tmp_path / "3").iterdir()] == ["p17_screenshot.webp"]
    assert Path(draft.final_path).read_bytes() == b"old"


def test_discarding_a_draft_never_written_is_fine(tmp_path: Path) -> None:
    files = LocalMediaFiles(str(tmp_path))

    files.discard(files.draft(3, 17, "audio.m4a"))

    assert list((tmp_path / "3").iterdir()) == []
