"""The app never asks Anki whether a word is learned: no maturity code is left anywhere."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCANNED_ROOTS = (REPO_ROOT / "backend" / "src", REPO_ROOT / "frontends" / "web" / "src")
SCANNED_SUFFIXES = {".py", ".ts", ".tsx", ".css"}
BANNED = re.compile(r"matur|note_cards|check-progress|check progress|from_anki", re.IGNORECASE)


@pytest.mark.unit
def test_no_anki_maturity_left() -> None:
    offenders = sorted(
        f"{path.relative_to(REPO_ROOT).as_posix()}:{number}: {line.strip()}"
        for root in SCANNED_ROOTS
        for path in root.rglob("*")
        if path.suffix in SCANNED_SUFFIXES and "node_modules" not in path.parts
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if BANNED.search(line)
    )
    assert offenders == []
