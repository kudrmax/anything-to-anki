from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DictionaryEntry:
    """A cached dictionary entry with definition and IPA transcription."""

    lemma: str
    pos: str
    definition: str
    ipa: str | None
