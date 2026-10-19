"""The app never asks Anki whether a word is learned: no maturity code is left anywhere,
and the docs describe none of the status model that went with it."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCANNED_ROOTS = (REPO_ROOT / "backend" / "src", REPO_ROOT / "frontends" / "web" / "src")
SCANNED_SUFFIXES = {".py", ".ts", ".tsx", ".css"}
BANNED = re.compile(r"matur|note_cards|check-progress|check progress|from_anki", re.IGNORECASE)
# The docs of today: docs/*.md. docs/specs and docs/superpowers keep the history.
DOCS = REPO_ROOT / "docs"
BANNED_IN_DOCS = re.compile(
    BANNED.pattern
    + r"|anki_notes|AnkiNote|CheckAnkiProgress|check_anki_progress|is_decision|decision_kind"
    r"|set_word_status|set_decision|set_skipped|phrase_skipped|card_decision",
    re.IGNORECASE,
)


def _offenders(paths: list[Path], banned: re.Pattern[str]) -> list[str]:
    return sorted(
        f"{path.relative_to(REPO_ROOT).as_posix()}:{number}: {line.strip()}"
        for path in paths
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if banned.search(line)
    )


@pytest.mark.unit
def test_no_anki_maturity_left() -> None:
    code = [
        path for root in SCANNED_ROOTS for path in root.rglob("*")
        if path.suffix in SCANNED_SUFFIXES and "node_modules" not in path.parts
    ]
    assert _offenders(code, BANNED) == []


@pytest.mark.unit
def test_the_docs_describe_no_removed_status_model() -> None:
    assert _offenders(sorted(DOCS.glob("*.md")), BANNED_IN_DOCS) == []
