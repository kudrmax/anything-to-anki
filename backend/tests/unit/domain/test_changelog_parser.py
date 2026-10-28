from __future__ import annotations

from datetime import date

import pytest
from backend.domain.services.changelog_parser import ChangelogParser
from backend.domain.value_objects.app_version import AppVersion

pytestmark = pytest.mark.unit

FEATURE_ENTRY = """# Changelog

Intro line that is ignored.

## 0.3.0 — 2026-11-02

One sentence: what this release is about.

### Bulk add
Text about the big feature.
![](docs/images/changelog/0.3.0/bulk-add.png)

### New
- Something new

### No longer broken
- A fixed thing
"""


def test_entry_with_feature_and_standard_sections() -> None:
    [entry] = ChangelogParser().parse(FEATURE_ENTRY)

    assert entry.version == AppVersion(0, 3, 0)
    assert entry.released_on == date(2026, 11, 2)
    assert entry.summary == "One sentence: what this release is about."
    assert [section.title for section in entry.sections] == ["Bulk add", "New", "No longer broken"]
    assert "![](docs/images/changelog/0.3.0/bulk-add.png)" in entry.sections[0].body_markdown
    assert entry.sections[1].body_markdown == "- Something new"


def test_entry_with_summary_only() -> None:
    [entry] = ChangelogParser().parse("## 1.0.1 — 2026-12-01\n\nJust a tweak.\n")

    assert entry.summary == "Just a tweak."
    assert entry.sections == ()


def test_two_entries_newest_first() -> None:
    text = "## 1.1.0 — 2026-12-02\n\nSecond.\n\n### New\n- b\n\n## 1.0.0 — 2026-12-01\n\nFirst.\n"

    entries = ChangelogParser().parse(text)

    assert [entry.version for entry in entries] == [AppVersion(1, 1, 0), AppVersion(1, 0, 0)]
    assert [entry.summary for entry in entries] == ["Second.", "First."]


def test_bad_heading_names_line() -> None:
    with pytest.raises(ValueError, match="## One point oh"):
        ChangelogParser().parse("# Changelog\n\n## One point oh\n")


def test_bad_date_names_line() -> None:
    with pytest.raises(ValueError, match="2026-13-45"):
        ChangelogParser().parse("## 1.0.0 — 2026-13-45\n")
