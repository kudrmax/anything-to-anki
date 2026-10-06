from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidClozeError
from backend.domain.services.phrase_target import WORD_EDGE_PUNCTUATION, normalize_target
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.stored_candidate import StoredCandidate

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
    """A word of the phrase as the user toggles it: text as written, punctuation included."""

    index: int
    text: str
    is_target: bool


@dataclass(frozen=True)
class ClozeFrontPart:
    """A piece of the card front: plain phrase text or a gap as Anki shows it."""

    text: str
    is_gap: bool


@dataclass(frozen=True)
class _Split:
    lead: str
    core: str
    tail: str


@dataclass(frozen=True)
class _Token:
    """A word of the phrase or a run of adjacent hidden words merged into one gap."""

    lead: str
    core: str
    tail: str
    is_gap: bool


def _split(word: str) -> _Split:
    core = word.strip(WORD_EDGE_PUNCTUATION)
    if not core:
        return _Split("", word, "")
    start = word.index(core)
    return _Split(word[:start], core, word[start + len(core) :])


def _escape(text: str) -> str:
    return text.replace(_ANKI_SEPARATOR, _ESCAPED_SEPARATOR).replace(_ANKI_CLOSE, _ESCAPED_CLOSE)


def _plain(text: str | None) -> str:
    return _MARKDOWN_BOLD.sub(r"\1", text).strip() if text else ""


def _leaks(text: str, hidden: list[str]) -> bool:
    return any(
        re.search(rf"\b{re.escape(word)}\b", text, re.IGNORECASE) for word in hidden if word
    )


class ClozeBuilder:
    """Turns a phrase plus hidden word indices into cloze text, preview and hint."""

    def words(self, phrase: str, lemma: str, surface_form: str | None) -> list[ClozeWord]:
        target = {w.lower() for w in normalize_target(surface_form or lemma).split()}
        lemma_words = {w.lower() for w in normalize_target(lemma).split()}
        result: list[ClozeWord] = []
        for index, text in enumerate(phrase.split()):
            core = _split(text).core.lower()
            result.append(ClozeWord(index, text, core in target or core in lemma_words))
        return result

    def default_hidden(self, words: list[ClozeWord]) -> tuple[int, ...]:
        return tuple(w.index for w in words if w.is_target)

    def validate(self, words: list[ClozeWord], indices: tuple[int, ...]) -> None:
        if not indices:
            raise InvalidClozeError("Hide at least one word")
        if any(i < 0 or i >= len(words) for i in indices):
            raise InvalidClozeError("Hidden word is out of the phrase")

    def cloze_text(
        self, phrase: str, indices: tuple[int, ...], hints: Sequence[str] = (),
    ) -> str:
        """Anki cloze markup; a gap with a hint becomes `{{c1::word::hint}}`."""

        def gap(core: str, number: int) -> str:
            hint = _hint_at(hints, number)
            suffix = _ANKI_SEPARATOR + _escape(hint) if hint else ""
            return "{{c1::" + _escape(core) + suffix + "}}"

        return self._render(phrase, indices, gap)

    def front(
        self, phrase: str, indices: tuple[int, ...], hints: Sequence[str] = (),
    ) -> list[ClozeFrontPart]:
        """The card front as Anki shows it: a gap is `[hint]`, or `[…]` without a hint."""
        parts: list[ClozeFrontPart] = []
        text = ""
        gaps = 0
        for position, token in enumerate(self._tokens(phrase, indices)):
            text += (" " if position else "") + token.lead
            if token.is_gap:
                hint = _hint_at(hints, gaps)
                gaps += 1
                if text:
                    parts.append(ClozeFrontPart(text, is_gap=False))
                parts.append(ClozeFrontPart(f"[{hint}]" if hint else GAP, is_gap=True))
                text = ""
            else:
                text += token.core
            text += token.tail
        if text:
            parts.append(ClozeFrontPart(text, is_gap=False))
        return parts

    def highlight_hidden(self, phrase: str, indices: tuple[int, ...]) -> str:
        return self._render(phrase, indices, lambda core, _number: f"<b>{core}</b>")

    def hidden_words(self, phrase: str, indices: tuple[int, ...]) -> list[str]:
        hidden = set(indices)
        return [_split(w).core for i, w in enumerate(phrase.split()) if i in hidden]

    def gap_hints(
        self,
        kind: ClozeHintKind,
        meaning: CandidateMeaning | None,
        phrase: str,
        indices: tuple[int, ...],
        custom: str | None,
    ) -> list[str]:
        """The hint of each gap in phrase order.

        First letters go to every gap for its own words; any other hint is about
        the whole target, so only the first gap carries it.
        """
        gaps = [token.core for token in self._tokens(phrase, indices) if token.is_gap]
        if kind is ClozeHintKind.FIRST_LETTER:
            return [
                self.hint_text(kind, meaning, [_split(w).core for w in core.split()], custom)
                for core in gaps
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
        cloze = candidate.cloze
        if cloze is None:
            return None
        phrase = candidate.card_phrase
        if cloze.phrase == phrase:
            return cloze
        hidden = self.default_hidden(self.words(phrase, candidate.lemma, candidate.surface_form))
        if not hidden:
            return None
        return replace(cloze, hidden_word_indices=hidden, phrase=phrase)

    def _render(
        self, phrase: str, indices: tuple[int, ...], gap: Callable[[str, int], str],
    ) -> str:
        out: list[str] = []
        gaps = 0
        for token in self._tokens(phrase, indices):
            if token.is_gap:
                out.append(token.lead + gap(token.core, gaps) + token.tail)
                gaps += 1
            else:
                out.append(token.core)
        return " ".join(out)

    @staticmethod
    def _tokens(phrase: str, indices: tuple[int, ...]) -> list[_Token]:
        """Adjacent hidden words become one gap; punctuation around a run stays outside."""
        hidden = set(indices)
        words = phrase.split()
        tokens: list[_Token] = []
        i = 0
        while i < len(words):
            if i not in hidden:
                tokens.append(_Token("", words[i], "", is_gap=False))
                i += 1
                continue
            run_end = i
            while run_end + 1 < len(words) and run_end + 1 in hidden:
                run_end += 1
            first, last = _split(words[i]), _split(words[run_end])
            middle = words[i + 1 : run_end]
            if i == run_end:
                core = first.core
            else:
                core = " ".join([first.core + first.tail, *middle, last.lead + last.core])
            tokens.append(_Token(first.lead, core, last.tail, is_gap=True))
            i = run_end + 1
        return tokens


def _hint_at(hints: Sequence[str], number: int) -> str:
    return hints[number] if number < len(hints) else ""
