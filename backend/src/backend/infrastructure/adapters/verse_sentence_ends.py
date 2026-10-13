from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.domain.ports.text_analyzer import TextAnalyzer

# A line ending in a word may end its sentence; one ending in punctuation speaks for itself.
_ENDS_IN_WORD_RE = re.compile(r"\w$")

# POS tags of words that syntactically require continuation (Tier 1 enjambment check)
_ENJAMBMENT_POS: frozenset[str] = frozenset({"ADP", "DET", "CCONJ", "SCONJ", "PART", "AUX"})

# Dependency labels checked when a token in line2 depends on a token in line1
_SYNTACTIC_DEPS: frozenset[str] = frozenset({
    "nsubj", "nsubjpass", "dobj", "obj", "iobj",
    "xcomp", "relcl", "acl", "advcl",
    "prep", "pobj", "acomp", "attr",
})


class VerseSentenceEnds:
    """Tells which lines of a song or a poem end their sentence.

    A line ending in a word ends its sentence unless the sentence runs on (enjambment):
      Tier 1 — its last content word requires continuation (preposition, determiner,
               conjunction, particle);
      Tier 2 — parsed together with the next line, a dependency arc crosses the boundary.
    Lines ending in punctuation are left to the parser.
    """

    def __init__(self, text_analyzer: TextAnalyzer) -> None:
        self._text_analyzer = text_analyzer

    def ends(self, lines: Sequence[str]) -> list[bool]:
        return [self._ends(line, lines[i + 1] if i + 1 < len(lines) else None)
                for i, line in enumerate(lines)]

    def _ends(self, line: str, next_line: str | None) -> bool:
        if not line or not _ENDS_IN_WORD_RE.search(line):
            return False
        line_tokens = self._text_analyzer.analyze(line)
        content_tokens = [t for t in line_tokens if not t.is_punct]
        if content_tokens and content_tokens[-1].pos in _ENJAMBMENT_POS:
            return False
        return not (next_line and self._is_enjambment(line, next_line, len(line_tokens)))

    def _is_enjambment(self, line1: str, line2: str, n1: int) -> bool:
        """Return True if line1 syntactically continues into line2."""
        tokens = self._text_analyzer.analyze(line1 + " " + line2)
        for token in tokens:
            if token.is_punct or token.index == token.head_index:
                continue
            if token.index >= n1 and token.head_index < n1 and token.dep in _SYNTACTIC_DEPS:
                return True
        return False
