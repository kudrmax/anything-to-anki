from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CambridgeSense:
    """A single sense (meaning) of a Cambridge dictionary entry."""

    definition: str
    level: str  # "A1", "B2", "" (empty if unassigned)
    examples: list[str]
    labels_and_codes: list[str]
    usages: list[str]
    domains: list[str]
    regions: list[str]
    image_link: str


@dataclass(frozen=True)
class CambridgeEntry:
    """A headword entry with pronunciation and senses."""

    headword: str
    pos: list[str]  # ["noun"], ["verb"], ["phrasal verb"]
    uk_ipa: list[str]
    us_ipa: list[str]
    uk_audio: list[str]
    us_audio: list[str]
    senses: list[CambridgeSense]


@dataclass(frozen=True)
class CambridgeWord:
    """Top-level record: a word with all its entries."""

    word: str
    entries: list[CambridgeEntry]
