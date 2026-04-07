from __future__ import annotations

import re
from typing import TYPE_CHECKING

from backend.domain.ports.source_parser import SourceParser

if TYPE_CHECKING:
    from backend.domain.ports.text_analyzer import TextAnalyzer

# Lines ending with a word character need a sentence-ending period
_NEEDS_PERIOD_RE = re.compile(r"\w$")

# POS tags of words that syntactically require continuation (Tier 1 enjambment check)
_ENJAMBMENT_POS: frozenset[str] = frozenset({"ADP", "DET", "CCONJ", "SCONJ", "PART", "AUX"})

# Dependency labels checked when a token in line2 depends on a token in line1
_SYNTACTIC_DEPS: frozenset[str] = frozenset({
    "nsubj", "nsubjpass", "dobj", "obj", "iobj",
    "xcomp", "relcl", "acl", "advcl",
    "prep", "pobj", "acomp", "attr",
})


class RegexLyricsParser(SourceParser):
    """Adds sentence-ending periods to lyrics lines to help sentence boundary detection."""

    def __init__(self, text_analyzer: TextAnalyzer) -> None:
        self._text_analyzer = text_analyzer

    def parse(self, raw_text: str) -> str:
        """Ensure each logical sentence line ends with punctuation."""
        return self._ensure_line_punctuation(raw_text)

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
        """Return True if line1 syntactically continues into line2."""
        tokens = self._text_analyzer.analyze(line1 + " " + line2)
        for token in tokens:
            if token.is_punct or token.index == token.head_index:
                continue
            if token.index >= n1 and token.head_index < n1 and token.dep in _SYNTACTIC_DEPS:
                return True
        return False
