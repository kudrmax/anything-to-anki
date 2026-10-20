from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.decision_rules import UnknownMark, unknown_mark

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from backend.application.utils.knowledge_scope import KnowledgeScope, KnowledgeSnapshot
    from backend.domain.entities.known_word import KnownWord
    from backend.domain.entities.unknown_word import UnknownWord
    from backend.domain.ports.word_mark_repository import WordMarkRepository
    from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
    from backend.domain.value_objects.vocabulary import Vocabulary


class UserVocabulary:
    """The only way to ask what words the user knows and is learning, and to mark them.

    Behind it are the word marks: a word is marked Known (in some parts of speech) or
    Unknown, never both; marking it one way takes the other mark off. Learning words come
    from the decisions and their Anki bindings; an exported word reads Known 30 days after
    its export. A word learned is never marked unknown (`unknown_mark`), and a Learn takes it
    out of unknown. Every read goes through the request's knowledge scope, and every write
    here makes it read anew.
    """

    def __init__(
        self,
        word_mark_repo: WordMarkRepository,
        scope: KnowledgeScope,
    ) -> None:
        self.__word_marks = word_mark_repo
        self.__scope = scope
        self.__marks: Mapping[UnknownMark, Callable[[str], None]] = {
            UnknownMark.MARK: self.__put_in_unknown,
            UnknownMark.REMOVE_KNOWN_FIRST: self.__leave,
            UnknownMark.IGNORE: self.__leave,
        }

    @property
    def scope(self) -> KnowledgeScope:
        return self.__scope

    def snapshot(self) -> Vocabulary:
        """What the user knows right now, for checking many words at once."""
        return self.__scope.snapshot().vocabulary()

    def knowledge(self) -> KnowledgeSnapshot:
        return self.__scope.snapshot()

    def of(self, lemma: str) -> LemmaKnowledge:
        return self.__scope.of(lemma)

    def is_known(self, lemma: str) -> bool:
        return self.__scope.of(lemma).is_known

    def mark_known(self, lemma: str, pos: str | None) -> None:
        self.__word_marks.mark_known(lemma, pos)
        self.__scope.invalidate()

    def forget_every_pos(self, lemma: str) -> None:
        """Undo of Known makes the word not known: every POS of the lemma goes."""
        self.__word_marks.remove_known(lemma)
        self.__scope.invalidate()

    def mark_unknown(self, lemma: str) -> UnknownMark:
        """Marks the lemma Unknown as its rule says. REMOVE_KNOWN_FIRST writes nothing: the
        caller runs the Known removal and asks again."""
        mark = unknown_mark(self.of(lemma))
        self.__marks[mark](lemma)
        return mark

    def forget_unknown(self, lemma: str) -> None:
        self.__word_marks.remove_unknown(lemma)
        self.__scope.invalidate()

    def __put_in_unknown(self, lemma: str) -> None:
        self.__word_marks.mark_unknown(lemma)
        self.__scope.invalidate()

    def __leave(self, lemma: str) -> None:
        """A word the user learns already says they don't know it; a Known one waits for
        its Known removal."""

    def known_words(self) -> list[KnownWord]:
        return self.__word_marks.known_entries()

    def unknown_words(self) -> list[UnknownWord]:
        return self.__word_marks.unknown_entries()

    def remove_known_entry(self, lemma: str, pos: str | None) -> None:
        """One entry of the Known list; the lemma's last one takes its Known mark off."""
        self.__word_marks.remove_known_entry(lemma, pos)
        self.__scope.invalidate()

    def known_count(self) -> int:
        """Distinct lemmas Known by the list or by the timer."""
        return len(self.__scope.snapshot().known_lemmas())

    def unknown_count(self) -> int:
        return self.__word_marks.unknown_count()
