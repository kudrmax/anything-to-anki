from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.known_word_dtos import KnownWordDTO

if TYPE_CHECKING:
    from backend.application.utils.decision_effects import DecisionEffects
    from backend.application.utils.user_vocabulary import UserVocabulary


class ManageKnownWordsUseCase:
    """The Known list: the words the user put there and the words Known by their 30 days in
    Anki. Deletes and adds entries; a word Known by its timer leaves Known by its lemma."""

    def __init__(
        self,
        vocabulary: UserVocabulary,
        effects: DecisionEffects,
    ) -> None:
        self._vocabulary = vocabulary
        self._effects = effects

    def list_all(self) -> list[KnownWordDTO]:
        listed = [
            KnownWordDTO(
                id=w.id,
                lemma=w.lemma,
                pos=w.pos,
                created_at=w.created_at,
            )
            for w in self._vocabulary.known_words()
        ]
        by_timer = [
            KnownWordDTO(
                id=None, lemma=lemma, pos=None, created_at=knowledge.timer_known_on,
                by_timer=True,
            )
            for lemma, knowledge in self._vocabulary.knowledge().lemmas()
            if knowledge.timer_known and knowledge.timer_known_on is not None
        ]
        return listed + by_timer

    def delete(self, known_word_id: int) -> None:
        """An entry edit, unless it is the lemma's last: then the word leaves Known as any
        removal does (§2.7), and its cards that read Known turn new in every source."""
        entries = self._vocabulary.known_words()
        entry = next((e for e in entries if e.id == known_word_id), None)
        if entry is None or any(e.lemma == entry.lemma and e.id != entry.id for e in entries):
            self._vocabulary.remove_known(known_word_id)
            return
        self._effects.known_removed(entry.lemma, self._vocabulary.of(entry.lemma))

    def delete_timer_known(self, lemma: str) -> None:
        """Decided (c): the word leaves Known as any removal does — its cards that read
        Known turn new in every source, and their notes stay in Anki. Nothing happens to a
        word not Known by its timer."""
        before = self._vocabulary.of(lemma)
        if not before.timer_known:
            return
        self._effects.known_removed(lemma, before)

    def add_bulk(self, lemmas: list[str]) -> None:
        """Add multiple words as known (pos=None, meaning known for any POS)."""
        for lemma in lemmas:
            self._vocabulary.mark_known(lemma, None)
