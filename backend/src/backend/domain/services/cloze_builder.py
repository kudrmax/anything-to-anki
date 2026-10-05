from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidClozeError
from backend.domain.services.phrase_target import WORD_EDGE_PUNCTUATION, normalize_target
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

if TYPE_CHECKING:
    from collections.abc import Callable

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
_ZERO_WIDTH_SPACE = "​"
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
class _Split:
    lead: str
    core: str
    tail: str


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

    def cloze_text(self, phrase: str, indices: tuple[int, ...]) -> str:
        return self._render(phrase, indices, lambda core: "{{c1::" + _escape(core) + "}}")

    def front_preview(self, phrase: str, indices: tuple[int, ...]) -> str:
        return self._render(phrase, indices, lambda _core: GAP)

    def highlight_hidden(self, phrase: str, indices: tuple[int, ...]) -> str:
        return self._render(phrase, indices, lambda core: f"<b>{core}</b>")

    def hidden_words(self, phrase: str, indices: tuple[int, ...]) -> list[str]:
        hidden = set(indices)
        return [_split(w).core for i, w in enumerate(phrase.split()) if i in hidden]

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

    def _render(self, phrase: str, indices: tuple[int, ...], gap: Callable[[str], str]) -> str:
        """Adjacent hidden words become one gap; punctuation around a run stays outside."""
        hidden = set(indices)
        words = phrase.split()
        out: list[str] = []
        i = 0
        while i < len(words):
            if i not in hidden:
                out.append(words[i])
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
            out.append(first.lead + gap(core) + last.tail)
            i = run_end + 1
        return " ".join(out)
