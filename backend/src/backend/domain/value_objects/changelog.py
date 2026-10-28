from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from backend.domain.value_objects.app_version import AppVersion


@dataclass(frozen=True)
class ChangelogSection:
    """One `###` block of a release: a big feature or a standard group such as "New"."""

    title: str
    body_markdown: str


@dataclass(frozen=True)
class ChangelogEntry:
    """One released version: its one-line summary and sections, in file order."""

    version: AppVersion
    released_on: date
    summary: str
    sections: tuple[ChangelogSection, ...]
