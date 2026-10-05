from __future__ import annotations

from enum import StrEnum


class ExportGroup(StrEnum):
    """Cards waiting for export, split by whether they have every required part."""

    READY = "ready"
    INCOMPLETE = "incomplete"
