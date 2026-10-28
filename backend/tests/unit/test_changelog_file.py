"""The repository's CHANGELOG.md: the app parses it as it is, and its newest entry is the
version being released. The release skill runs this before tagging."""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from backend.domain.services.changelog_parser import ChangelogParser
from backend.domain.value_objects.app_version import AppVersion

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_changelog_parses_and_its_top_entry_is_the_project_version() -> None:
    entries = ChangelogParser().parse((REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    with (REPO_ROOT / "pyproject.toml").open("rb") as pyproject:
        version = AppVersion.parse(tomllib.load(pyproject)["project"]["version"])

    if entries:
        assert entries[0].version == version
