from __future__ import annotations

import re

from backend.domain.ports.text_analyzer import TextAnalyzer
from backend.domain.ports.text_cleaner import TextCleaner
from backend.domain.value_objects.source_type import SourceType

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

# Lines ending with a word character need a sentence-ending period
_NEEDS_PERIOD_RE = re.compile(r"\w$")

# POS tags of words that syntactically require continuation (Tier 1 enjambment check)
_ENJAMBMENT_POS: frozenset[str] = frozenset({"ADP", "DET", "CCONJ", "SCONJ", "PART", "AUX"})

# Dependency labels checked when a token in line2 depends on a token in line1
# (direction: dependent-in-line2 → head-in-line1 only).
_SYNTACTIC_DEPS: frozenset[str] = frozenset({
    "nsubj", "nsubjpass", "dobj", "obj", "iobj",
    "xcomp", "relcl", "acl", "advcl",
    "prep", "pobj", "acomp", "attr",
})


class RegexTextCleaner(TextCleaner):
    """Cleans raw text by removing timecodes, tags, duplicates, and normalizing whitespace."""

    def __init__(self, text_analyzer: TextAnalyzer) -> None:
        self._text_analyzer = text_analyzer

    def clean(self, raw_text: str, source_type: SourceType = SourceType.TEXT) -> str:
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

        # For lyrics: add sentence-ending period to bare lines so spaCy detects boundaries
        if source_type == SourceType.LYRICS:
            text = self._ensure_line_punctuation(text)

        return text.strip()

    def _ensure_line_punctuation(self, text: str) -> str:
        """Append '.' to lines that end a sentence, skip lines with enjambment.

        For lyrics/poetry: lines ending with \\w are checked in two tiers:
          Tier 1 — if the last content word has a POS that requires continuation
                   (preposition, determiner, conjunction, particle) → enjambment.
          Tier 2 — parse the pair (line_i + line_{i+1}) and check if any syntactic
                   dependency arc crosses the line boundary → enjambment.
        Lines already ending with punctuation are left untouched.
        """
        lines = text.splitlines()
        result: list[str] = []
        for i, line in enumerate(lines):
            if not line or not _NEEDS_PERIOD_RE.search(line):
                result.append(line)
                continue

            # Tier 1: analyze current line, check POS of last content word
            line_tokens = self._text_analyzer.analyze(line)
            n1 = len(line_tokens)
            content_tokens = [t for t in line_tokens if not t.is_punct]
            if content_tokens and content_tokens[-1].pos in _ENJAMBMENT_POS:
                result.append(line)
                continue

            # Tier 2: pair analysis — check dep arcs crossing the line boundary
            next_line = lines[i + 1] if i + 1 < len(lines) else None
            if next_line and self._is_enjambment(line, next_line, n1):
                result.append(line)
            else:
                result.append(line + ".")
        return "\n".join(result)

    def _is_enjambment(self, line1: str, line2: str, n1: int) -> bool:
        """Return True if line1 syntactically continues into line2.

        Combines both lines and checks for dependency arcs where a token from
        line2 depends on a token in line1 (dependent-in-line2 → head-in-line1).
        Only this direction is checked to avoid false positives from spaCy
        connecting independent sentences in the opposite direction.
        """
        tokens = self._text_analyzer.analyze(line1 + " " + line2)
        for token in tokens:
            if token.is_punct or token.index == token.head_index:
                continue
            if token.index >= n1 and token.head_index < n1 and token.dep in _SYNTACTIC_DEPS:
                return True
        return False

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
