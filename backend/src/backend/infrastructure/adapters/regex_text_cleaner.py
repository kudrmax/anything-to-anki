from __future__ import annotations

import re

from backend.domain.ports.text_cleaner import TextCleaner

# Timecodes: [00:01:23], [1:23], [00:01:23.456], [00:01:23,456]
_TIMECODE_RE = re.compile(r"\[\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\]")

# Service tags: [Music], [Applause], [Laughter], etc.
_SERVICE_TAG_RE = re.compile(r"\[(?:Music|Applause|Laughter|Cheering|Silence)\]", re.IGNORECASE)

# Song structure tags: [Verse 1], [Chorus], [Bridge], [Intro], [Outro], [Hook], [Pre-Chorus], etc.
_SONG_STRUCTURE_RE = re.compile(
    r"\[(?:Verse|Chorus|Bridge|Intro|Outro|Hook|Pre-Chorus|Refrain|Interlude|Breakdown|Coda)"
    r"(?:\s+\d+)?\]",
    re.IGNORECASE,
)

# Musical symbols
_MUSIC_SYMBOLS_RE = re.compile(r"[♪♫♬♩]+")

# BOM and invisible unicode
_INVISIBLE_RE = re.compile(r"[\ufeff\u200b\u200c\u200d\u00ad\u2060]")

# Multiple blank lines → single newline
_MULTI_NEWLINES_RE = re.compile(r"\n{3,}")

# Multiple spaces → single space
_MULTI_SPACES_RE = re.compile(r"[ \t]{2,}")


class RegexTextCleaner(TextCleaner):
    """Cleans raw text by removing timecodes, tags, duplicates, and normalizing whitespace."""

    def clean(self, raw_text: str) -> str:
        text = raw_text

        # Remove BOM and invisible characters
        text = _INVISIBLE_RE.sub("", text)

        # Remove timecodes
        text = _TIMECODE_RE.sub("", text)

        # Remove service tags
        text = _SERVICE_TAG_RE.sub("", text)

        # Remove song structure tags
        text = _SONG_STRUCTURE_RE.sub("", text)

        # Remove musical symbols
        text = _MUSIC_SYMBOLS_RE.sub("", text)

        # Remove duplicate lines
        text = self._remove_duplicate_lines(text)

        # Normalize whitespace
        text = _MULTI_SPACES_RE.sub(" ", text)
        text = _MULTI_NEWLINES_RE.sub("\n\n", text)

        # Strip each line and remove empty lines
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        text = "\n".join(lines)

        return text.strip()

    def _remove_duplicate_lines(self, text: str) -> str:
        """Remove consecutive duplicate lines."""
        lines = text.splitlines()
        result: list[str] = []
        prev = ""
        for line in lines:
            stripped = line.strip()
            if stripped != prev or not stripped:
                result.append(line)
            prev = stripped
        return "\n".join(result)
