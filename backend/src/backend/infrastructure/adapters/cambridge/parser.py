from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from backend.infrastructure.adapters.cambridge.models import (
    CambridgeEntry,
    CambridgeSense,
    CambridgeWord,
)

logger = logging.getLogger(__name__)


def _parse_sense(raw: dict[str, Any]) -> CambridgeSense:
    return CambridgeSense(
        definition=raw.get("definition", ""),
        level=raw.get("level", ""),
        examples=raw.get("examples", []),
        labels_and_codes=raw.get("labels_and_codes", []),
        usages=raw.get("usages", []),
        domains=raw.get("domains", []),
        regions=raw.get("regions", []),
        image_link=raw.get("image_link", ""),
    )


def _parse_entry(raw: dict[str, Any]) -> CambridgeEntry:
    return CambridgeEntry(
        headword=raw.get("headword", ""),
        pos=raw.get("pos", []),
        uk_ipa=raw.get("uk_ipa", []),
        us_ipa=raw.get("us_ipa", []),
        uk_audio=raw.get("uk_audio", []),
        us_audio=raw.get("us_audio", []),
        senses=[_parse_sense(s) for s in raw.get("senses", [])],
    )


def _parse_word(raw: dict[str, Any]) -> CambridgeWord | None:
    word = raw.get("word")
    entries_raw = raw.get("entries")
    if not isinstance(word, str) or not isinstance(entries_raw, list):
        return None
    return CambridgeWord(
        word=word,
        entries=[_parse_entry(e) for e in entries_raw],
    )


def parse_cambridge_jsonl(path: Path) -> dict[str, CambridgeWord]:
    """Parse cambridge.jsonl into a dict keyed by word.

    Returns empty dict if file is missing. Skips malformed lines.
    """
    if not path.exists():
        logger.warning("Cambridge dictionary not found at %s — skipping", path)
        return {}

    result: dict[str, CambridgeWord] = {}
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Cambridge JSONL: bad JSON at line %d — skipped", line_num)
                continue
            parsed = _parse_word(raw)
            if parsed is None:
                logger.warning(
                    "Cambridge JSONL: malformed record at line %d — skipped", line_num,
                )
                continue
            result[parsed.word] = parsed

    logger.info("Cambridge dictionary loaded: %d words", len(result))
    return result
