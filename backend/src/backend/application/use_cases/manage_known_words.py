from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

from backend.application.dto.known_word_dtos import KnownWordDTO
from backend.domain.exceptions import KnownWordNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from backend.application.utils.decision_effects import DecisionEffects
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.unit_of_work import UnitOfWork


class ManageKnownWordsUseCase:
    """The Known list, newest first: the words the user put there and the words Known by
    their 30 days in Anki. Deletes and adds entries; a word Known by its timer leaves Known
    by its lemma."""

    def __init__(
        self,
        vocabulary: UserVocabulary,
        effects: DecisionEffects,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._vocabulary = vocabulary
        self._effects = effects

    def list_all(self) -> list[KnownWordDTO]:
        listed = [
            KnownWordDTO(
                id=w.id,
                lemma=w.lemma,
                pos=w.pos,
                created_at=w.created_at,
                removal_key=_key(_ENTRY, w.id),
            )
            for w in self._vocabulary.known_words()
        ]
        by_timer = [
            KnownWordDTO(
                id=None, lemma=lemma, pos=None, created_at=knowledge.timer_known_on,
                removal_key=_key(_TIMER, lemma), by_timer=True,
            )
            for lemma, knowledge in self._vocabulary.knowledge().lemmas()
            if knowledge.timer_known and knowledge.timer_known_on is not None
        ]
        return sorted(listed + by_timer, key=lambda word: _aware(word.created_at), reverse=True)

    def remove(self, removal_key: str) -> None:
        """Removes the entry the list gave this key; raises KnownWordNotFoundError for a key
        it never gave."""
        kind, _, value = removal_key.partition(_SEPARATOR)
        removals: dict[str, Callable[[str], None]] = {
            _ENTRY: self._delete_entry, _TIMER: self._delete_timer_known,
        }
        removal = removals.get(kind)
        if removal is None or not value:
            raise KnownWordNotFoundError(removal_key)
        with self._unit_of_work.write():
            removal(value)

    def _delete_entry(self, known_word_id: str) -> None:
        if not known_word_id.isdecimal():
            raise KnownWordNotFoundError(known_word_id)
        self._delete(int(known_word_id))

    def delete(self, known_word_id: int) -> None:
        """An entry edit, unless it is the lemma's last: then the word leaves Known as any
        removal does (§2.7), and its cards that read Known turn new in every source."""
        with self._unit_of_work.write():
            self._delete(known_word_id)

    def _delete(self, known_word_id: int) -> None:
        entries = self._vocabulary.known_words()
        entry = next((e for e in entries if e.id == known_word_id), None)
        if entry is None:
            return
        if any(e.lemma.lower() == entry.lemma.lower() and e.id != entry.id for e in entries):
            self._vocabulary.remove_known_entry(entry.lemma, entry.pos)
            return
        self._effects.known_removed(entry.lemma, self._vocabulary.of(entry.lemma))

    def delete_timer_known(self, lemma: str) -> None:
        """Decided (c): the word leaves Known as any removal does — its cards that read
        Known turn new in every source, and their notes stay in Anki. Nothing happens to a
        word not Known by its timer."""
        with self._unit_of_work.write():
            self._delete_timer_known(lemma)

    def _delete_timer_known(self, lemma: str) -> None:
        before = self._vocabulary.of(lemma)
        if not before.timer_known:
            return
        self._effects.known_removed(lemma, before)

    def add_bulk(self, lemmas: list[str]) -> None:
        """Add multiple words as known (pos=None, meaning known for any POS)."""
        with self._unit_of_work.write():
            for lemma in lemmas:
                self._vocabulary.mark_known(lemma, None)


_ENTRY, _TIMER, _SEPARATOR = "entry", "timer", ":"


def _key(kind: str, value: object) -> str:
    return f"{kind}{_SEPARATOR}{value}"


def _aware(moment: datetime) -> datetime:
    """SQLite gives naive UTC times, the timer gives aware ones: both compare as UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
