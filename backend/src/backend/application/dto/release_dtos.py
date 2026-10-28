from __future__ import annotations

from datetime import date  # noqa: TC003 — pydantic resolves field types at runtime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.domain.value_objects.changelog import ChangelogEntry, ChangelogSection


class ChangelogSectionDTO(BaseModel):
    title: str
    body_markdown: str

    @classmethod
    def from_section(cls, section: ChangelogSection) -> ChangelogSectionDTO:
        return cls(title=section.title, body_markdown=section.body_markdown)


class ChangelogEntryDTO(BaseModel):
    version: str
    released_on: date
    summary: str
    sections: list[ChangelogSectionDTO]

    @classmethod
    def from_entry(cls, entry: ChangelogEntry) -> ChangelogEntryDTO:
        return cls(
            version=str(entry.version),
            released_on=entry.released_on,
            summary=entry.summary,
            sections=[ChangelogSectionDTO.from_section(section) for section in entry.sections],
        )


class UpdateStatusDTO(BaseModel):
    """What the installed copy knows about newer releases. `entries` are the changes the
    update would bring; `check_failed` is set when an explicit check could not reach the
    releases."""

    current: str
    latest: str | None
    available: bool
    entries: list[ChangelogEntryDTO]
    check_failed: bool


UpdateState = Literal["idle", "running", "failed", "done"]


class UpdateStateDTO(BaseModel):
    """How the update started from the app is going; `log_tail` is filled once it failed."""

    state: UpdateState
    log_tail: str
