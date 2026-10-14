from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidClozeError
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.value_objects.phrase import Phrase

GAP = "[…]"
FIRST_LETTER_SUFFIX = "…"
ALWAYS_AVAILABLE = (ClozeHintKind.NONE, ClozeHintKind.FIRST_LETTER, ClozeHintKind.CUSTOM)
HINT_ORDER = (
    ClozeHintKind.NONE,
    ClozeHintKind.TRANSLATION,
    ClozeHintKind.SYNONYMS,
    ClozeHintKind.FIRST_LETTER,
    ClozeHintKind.CUSTOM,
)
_ZERO_WIDTH_SPACE = "\u200b"
_ANKI_SEPARATOR = "::"
_ANKI_CLOSE = "}}"
_ESCAPED_SEPARATOR = f":{_ZERO_WIDTH_SPACE}:"
_ESCAPED_CLOSE = f"}}{_ZERO_WIDTH_SPACE}}}"
_MARKDOWN_BOLD = re.compile(r"\*\*(.+?)\*\*")


@dataclass(frozen=True)
class ClozeWord:
    """A word of the phrase as the user toggles it."""

    index: int
    text: str
    is_target: bool


@dataclass(frozen=True)
class ClozeFrontPart:
    """A piece of the card front: plain phrase text or a gap as Anki shows it."""

    text: str
    is_gap: bool


def _escape(text: str) -> str:
    return text.replace(_ANKI_SEPARATOR, _ESCAPED_SEPARATOR).replace(_ANKI_CLOSE, _ESCAPED_CLOSE)


def _plain(text: str | None) -> str:
    return _MARKDOWN_BOLD.sub(r"\1", text).strip() if text else ""


def _leaks(text: str, hidden: list[str]) -> bool:
    return any(
        re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE) for word in hidden if word
    )


class ClozeBuilder:
    """Turns a phrase plus hidden word numbers into cloze text, preview and hint.

    Words and their numbers are the phrase's own; the text between gaps stays as written.
    """

    def words(self, phrase: Phrase) -> list[ClozeWord]:
        target = set(phrase.target)
        return [
            ClozeWord(index, phrase.word_text(index), index in target)
            for index in range(len(phrase.words))
        ]

    def default_hidden(self, phrase: Phrase) -> tuple[int, ...]:
        return phrase.target

    def validate(self, phrase: Phrase, indices: tuple[int, ...]) -> None:
        if not indices:
            raise InvalidClozeError("Hide at least one word")
        if any(i < 0 or i >= len(phrase.words) for i in indices):
            raise InvalidClozeError("Hidden word is out of the phrase")

    def cloze_text(
        self, phrase: Phrase, indices: tuple[int, ...], hints: Sequence[str] = (),
    ) -> str:
        """Anki cloze markup; a gap with a hint becomes `{{c1::word::hint}}`."""

        def gap(core: str, number: int) -> str:
            hint = _hint_at(hints, number)
            suffix = _ANKI_SEPARATOR + _escape(hint) if hint else ""
            return "{{c1::" + _escape(core) + suffix + "}}"

        return self._render(phrase, indices, gap)

    def front(
        self, phrase: Phrase, indices: tuple[int, ...], hints: Sequence[str] = (),
    ) -> list[ClozeFrontPart]:
        """The card front as Anki shows it: a gap is `[hint]`, or `[…]` without a hint."""
        parts: list[ClozeFrontPart] = []
        position = 0
        for number, (start, end) in enumerate(phrase.runs(indices)):
            if start > position:
                parts.append(ClozeFrontPart(phrase.text[position:start], is_gap=False))
            hint = _hint_at(hints, number)
            parts.append(ClozeFrontPart(f"[{hint}]" if hint else GAP, is_gap=True))
            position = end
        if position < len(phrase.text):
            parts.append(ClozeFrontPart(phrase.text[position:], is_gap=False))
        return parts

    def highlight_hidden(self, phrase: Phrase, indices: tuple[int, ...]) -> str:
        return self._render(phrase, indices, lambda core, _number: f"<b>{core}</b>")

    def hidden_words(self, phrase: Phrase, indices: tuple[int, ...]) -> list[str]:
        return [phrase.word_text(i) for i in sorted(set(indices)) if 0 <= i < len(phrase.words)]

    def gap_hints(
        self,
        kind: ClozeHintKind,
        meaning: CandidateMeaning | None,
        phrase: Phrase,
        indices: tuple[int, ...],
        custom: str | None,
    ) -> list[str]:
        """The hint of each gap in phrase order.

        First letters go to every gap for its own words; any other hint is about
        the whole target, so only the first gap carries it.
        """
        gaps = phrase.runs(indices)
        if kind is ClozeHintKind.FIRST_LETTER:
            hidden = sorted(set(indices))
            return [
                self.hint_text(kind, meaning, [
                    phrase.word_text(i) for i in hidden if start <= phrase.words[i].start < end
                ], custom)
                for start, end in gaps
            ]
        hint = self.hint_text(kind, meaning, [], custom)
        return [hint if number == 0 else "" for number in range(len(gaps))]

    def hint_text(
        self,
        kind: ClozeHintKind,
        meaning: CandidateMeaning | None,
        hidden: list[str],
        custom: str | None,
    ) -> str:
        if kind is ClozeHintKind.TRANSLATION:
            return _plain(meaning.translation if meaning else None)
        if kind is ClozeHintKind.SYNONYMS:
            return _plain(meaning.synonyms if meaning else None)
        if kind is ClozeHintKind.FIRST_LETTER:
            return " ".join(word[0] + FIRST_LETTER_SUFFIX for word in hidden if word)
        if kind is ClozeHintKind.CUSTOM:
            return (custom or "").strip()
        return ""

    def available_hints(
        self, meaning: CandidateMeaning | None, hidden: list[str]
    ) -> list[ClozeHintKind]:
        usable = set(ALWAYS_AVAILABLE)
        for kind in (ClozeHintKind.TRANSLATION, ClozeHintKind.SYNONYMS):
            text = self.hint_text(kind, meaning, hidden, None)
            if text and not _leaks(text, hidden):
                usable.add(kind)
        return [kind for kind in HINT_ORDER if kind in usable]

    def effective(self, candidate: StoredCandidate) -> CandidateCloze | None:
        """The markup for the phrase the card shows; for another phrase it is the target."""
        cloze = candidate.cloze
        if cloze is None:
            return None
        phrase = candidate.phrase
        if cloze.phrase == phrase.text:
            return cloze
        return replace(cloze, hidden_word_indices=phrase.target, phrase=phrase.text)

    def _render(
        self, phrase: Phrase, indices: tuple[int, ...], gap: Callable[[str, int], str],
    ) -> str:
        out: list[str] = []
        position = 0
        for number, (start, end) in enumerate(phrase.runs(indices)):
            out.append(phrase.text[position:start])
            out.append(gap(phrase.text[start:end], number))
            position = end
        out.append(phrase.text[position:])
        return "".join(out)


def _hint_at(hints: Sequence[str], number: int) -> str:
    return hints[number] if number < len(hints) else ""
