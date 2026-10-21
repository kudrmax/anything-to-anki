"""What the user knows, read once per request or job (design §2.2)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
from backend.domain.value_objects.vocabulary import Vocabulary

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
    from datetime import datetime

    from backend.domain.ports.clock import Clock
    from backend.domain.ports.learning_query import LearningQuery
    from backend.domain.ports.word_mark_repository import WordMarkRepository


class KnowledgeSnapshot:
    """The marks and the active bindings at one moment, lemma by lemma (lowercase)."""

    def __init__(
        self,
        now: datetime,
        *,
        known: frozenset[str],
        unknown: frozenset[str],
        awaiting_export: frozenset[str],
        active_since: Mapping[str, tuple[datetime, ...]],
    ) -> None:
        self._now = now
        self._known = known
        self._unknown = unknown
        self._awaiting = awaiting_export
        self._active = active_since
        self._lemmas = known | unknown | awaiting_export | frozenset(active_since)

    def of(self, lemma: str) -> LemmaKnowledge:
        key = lemma.lower()
        return LemmaKnowledge.at(
            self._now,
            known_marked=key in self._known,
            unknown=key in self._unknown,
            learn_anywhere=key in self._awaiting,
            active_since=self._active.get(key, ()),
        )

    def lemmas(self) -> Iterator[tuple[str, LemmaKnowledge]]:
        """Every lemma in a list, waiting for export or in Anki, in alphabetical order."""
        for lemma in sorted(self._lemmas):
            yield lemma, self.of(lemma)

    def known_lemmas(self) -> frozenset[str]:
        """Known by the list or by the timer."""
        return frozenset(lemma for lemma in self._lemmas if self.of(lemma).is_known)

    def vocabulary(self) -> Vocabulary:
        """known = Known by the list or the timer; learning = in Anki ∪ waiting for export."""
        knowledge = {lemma: self.of(lemma) for lemma in self._lemmas}
        return Vocabulary.of(
            known={lemma for lemma, k in knowledge.items() if k.is_known},
            unknown=self._unknown,
            learning={lemma for lemma, k in knowledge.items() if k.is_learning or k.is_learn},
        )


class KnowledgeScope:
    """One request's or job's view of what the user knows: one frozen `now`, one snapshot.

    Made once per database session (container.py). A vocabulary or binding write in the
    scope marks the snapshot stale; the next read rebuilds it with the same `now`. Nothing
    else reads the clock.
    """

    def __init__(
        self,
        clock: Clock,
        word_mark_repo: WordMarkRepository,
        learning_query: LearningQuery,
    ) -> None:
        self._clock = clock
        self._marks = word_mark_repo
        self._learning = learning_query
        self._now: datetime | None = None
        self._snapshot: KnowledgeSnapshot | None = None

    @property
    def now(self) -> datetime:
        if self._now is None:
            self._now = self._clock.now()
        return self._now

    def snapshot(self) -> KnowledgeSnapshot:
        if self._snapshot is None:
            self._snapshot = KnowledgeSnapshot(
                self.now,
                known=frozenset(self._marks.known_lemmas()),
                unknown=frozenset(self._marks.unknown_lemmas()),
                awaiting_export=frozenset(self._learning.awaiting_export()),
                active_since=self._learning.active_since(),
            )
        return self._snapshot

    def of(self, lemma: str) -> LemmaKnowledge:
        return self.snapshot().of(lemma)

    def invalidate(self) -> None:
        self._snapshot = None
