from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.vocabulary import Vocabulary

if TYPE_CHECKING:
    from backend.domain.entities.known_word import KnownWord
    from backend.domain.entities.unknown_word import UnknownWord
    from backend.domain.ports.known_word_removal_repository import KnownWordRemovalRepository
    from backend.domain.ports.known_word_repository import KnownWordRepository
    from backend.domain.ports.learning_query import LearningQuery
    from backend.domain.ports.unknown_word_repository import UnknownWordRepository


class UserVocabulary:
    """The only way to ask what words the user knows and is learning, and to mark them.

    Behind it are two lists, known and unknown words. A word is in at most
    one: marking it in one list takes it out of the other. If it is in both
    anyway, it is unknown. Learning words come from the decisions and Anki notes;
    a word Anki says is learned becomes known, unless the user said otherwise.
    """

    def __init__(
        self,
        known_word_repo: KnownWordRepository,
        unknown_word_repo: UnknownWordRepository,
        learning_query: LearningQuery,
        removal_repo: KnownWordRemovalRepository,
    ) -> None:
        self.__known = known_word_repo
        self.__unknown = unknown_word_repo
        self.__learning = learning_query
        self.__removals = removal_repo

    def snapshot(self) -> Vocabulary:
        """What the user knows right now, for checking many words at once."""
        return Vocabulary.of(
            known={lemma for lemma, _ in self.__known.get_all_pairs()},
            unknown=self.__unknown.lemmas(),
            learning=self.__learning.learning_lemmas(),
        )

    def is_known(self, lemma: str) -> bool:
        return self.snapshot().is_known(lemma)

    def mark_known(self, lemma: str, pos: str | None) -> None:
        """The user's own Known: lifts an earlier removal, so maturity may count again."""
        self.__unknown.remove_by_lemma(lemma)
        self.__removals.discard(lemma)
        self.__known.add(lemma, pos)

    def forget_known(self, lemma: str, pos: str | None) -> None:
        """Takes back a Known a card decision added; not the user removing it from Known."""
        self.__known.remove_by_lemma(lemma, pos)

    def restore_unknown(self, lemma: str) -> None:
        """Puts back an Unknown a card decision took away."""
        self.__unknown.add(lemma)

    def start_learning(self, lemma: str) -> None:
        """A new Learn is a new intent: lifts an earlier removal from Known."""
        self.__removals.discard(lemma)

    def mark_mature(self, lemma: str, pos: str | None) -> bool:
        """Anki says the word is learned: Known, unless it is known already, the user marked it
        unknown or took it out of Known in the settings. Returns whether it was applied."""
        vocabulary = Vocabulary.of(
            known={word for word, _ in self.__known.get_all_pairs()},
            unknown=self.__unknown.lemmas(),
        )
        key = lemma.lower()
        if key in vocabulary.known or key in vocabulary.unknown:
            return False
        if self.__removals.contains(lemma):
            return False
        self.__known.add(lemma, pos, from_anki=True)
        return True

    def mark_unknown(self, lemma: str) -> None:
        self.__known.remove_every_pos(lemma)
        self.__unknown.add(lemma)

    def known_words(self) -> list[KnownWord]:
        return self.__known.list_all()

    def unknown_words(self) -> list[UnknownWord]:
        return self.__unknown.list_all()

    def remove_known(self, known_word_id: int) -> None:
        """The user takes the word out of Known: Anki maturity will not put it back."""
        word = self.__known.get_by_id(known_word_id)
        self.__known.remove(known_word_id)
        if word is not None:
            self.__removals.add(word.lemma)

    def remove_unknown(self, unknown_word_id: int) -> None:
        self.__unknown.remove(unknown_word_id)

    def known_count(self) -> int:
        return self.__known.count()

    def unknown_count(self) -> int:
        return self.__unknown.count()
