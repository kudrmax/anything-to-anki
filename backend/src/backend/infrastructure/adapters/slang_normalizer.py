from __future__ import annotations

import re

from backend.domain.ports.text_normalizer import TextNormalizer

# Each rule: (compiled_pattern, replacement_string)
# Order matters: specific rules first, general patterns last.
_SPECIFIC_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bwanna\b", re.IGNORECASE), "want to"),
    (re.compile(r"\bgunna\b", re.IGNORECASE), "going to"),
    (re.compile(r"\btryna\b", re.IGNORECASE), "trying to"),
    (re.compile(r"\bdunno\b", re.IGNORECASE), "do not know"),
    (re.compile(r"\blemme\b", re.IGNORECASE), "let me"),
    (re.compile(r"\bgimme\b", re.IGNORECASE), "give me"),
    (re.compile(r"\bcoulda\b", re.IGNORECASE), "could have"),
    (re.compile(r"\bwoulda\b", re.IGNORECASE), "would have"),
    (re.compile(r"\bshoulda\b", re.IGNORECASE), "should have"),
    (re.compile(r"\bkinda\b", re.IGNORECASE), "kind of"),
    (re.compile(r"\bsorta\b", re.IGNORECASE), "sort of"),
    (re.compile(r"\bwhatcha\b", re.IGNORECASE), "what are you"),
    (re.compile(r"\bgotcha\b", re.IGNORECASE), "got you"),
    (re.compile(r"\by'all\b", re.IGNORECASE), "you all"),
    # ain't is context-dependent (am/is/are/has/have not);
    # "is not" chosen as the most frequent default.
    (re.compile(r"\bain't\b", re.IGNORECASE), "is not"),
    # 'em: apostrophe is not a word char, so \b doesn't work before it;
    # match a space or start-of-string before the apostrophe.
    (re.compile(r"(?<!\w)'em\b", re.IGNORECASE), "them"),
)

# General pattern: dropped -g (goin' → going, doin' → doing).
# The trailing apostrophe is not a word char, so \b after it doesn't match;
# use a lookahead for whitespace or end-of-string instead.
_DROPPED_G_RE = re.compile(r"\b(\w+)in'(?=\s|$)")


def _match_case(original: str, replacement: str) -> str:
    """Preserve the case pattern of the original in the replacement."""
    if original.isupper():
        return replacement.upper()
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


class SlangNormalizer(TextNormalizer):
    """Expands informal English contractions using regex rules."""

    def normalize(self, text: str) -> str:
        """Apply all slang rules sequentially, preserving first-letter case."""
        result = text

        for pattern, replacement in _SPECIFIC_RULES:
            result = pattern.sub(
                lambda m, r=replacement: _match_case(m.group(0), r),
                result,
            )

        # General -in' → -ing (last, to avoid conflicting with specific rules)
        result = _DROPPED_G_RE.sub(lambda m: m.group(1) + "ing", result)

        return result
