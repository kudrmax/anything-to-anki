from __future__ import annotations

import re
from datetime import date

from backend.domain.value_objects.app_version import AppVersion
from backend.domain.value_objects.changelog import ChangelogEntry, ChangelogSection

ENTRY_PREFIX = "## "
SECTION_PREFIX = "### "
ENTRY_HEADING = re.compile(r"## (\S+) — (\d{4}-\d{2}-\d{2})")


class ChangelogParser:
    """Reads a CHANGELOG.md into entries, newest first as the file lists them."""

    def parse(self, text: str) -> list[ChangelogEntry]:
        entries: list[ChangelogEntry] = []
        heading: str | None = None
        block: list[str] = []
        for line in text.splitlines():
            if line.startswith(ENTRY_PREFIX):
                if heading is not None:
                    entries.append(self._entry(heading, block))
                heading, block = line, []
            elif heading is not None:
                block.append(line)
        if heading is not None:
            entries.append(self._entry(heading, block))
        return entries

    def _entry(self, heading: str, lines: list[str]) -> ChangelogEntry:
        match = ENTRY_HEADING.fullmatch(heading.rstrip())
        if match is None:
            raise ValueError(f"Malformed changelog heading: {heading!r}")
        try:
            version = AppVersion.parse(match.group(1))
            released_on = date.fromisoformat(match.group(2))
        except ValueError as error:
            raise ValueError(f"Malformed changelog heading: {heading!r} ({error})") from error
        summary_lines: list[str] = []
        titles: list[str] = []
        bodies: list[list[str]] = []
        for line in lines:
            if line.startswith(SECTION_PREFIX):
                titles.append(line[len(SECTION_PREFIX):].strip())
                bodies.append([])
            elif bodies:
                bodies[-1].append(line)
            else:
                summary_lines.append(line)
        sections = tuple(
            ChangelogSection(title, "\n".join(body).strip())
            for title, body in zip(titles, bodies, strict=True)
        )
        return ChangelogEntry(version, released_on, "\n".join(summary_lines).strip(), sections)
