"""How the stored projection of card state is derived: the other words of a phrase with
their newness, and when a card's state changes by itself."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.card_state_rows import PhraseWordRow
from backend.domain.value_objects.phrase_newness import PhraseNewness

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from backend.domain.value_objects.lemma_knowledge import LemmaKnowledge
    from backend.domain.value_objects.phrase import Phrase
    from backend.domain.value_objects.user_knowledge import KnowledgeBase


def phrase_word_rows(
    phrase_id: int, phrase: Phrase, knowledge_base: KnowledgeBase,
) -> tuple[PhraseWordRow, ...]:
    """The words of the phrase besides its target, in phrase order, each with its newness."""
    target = set(phrase.target)
    return tuple(
        PhraseWordRow(
            lemma=word.lemma.lower(),
            phrase_id=phrase_id,
            position=position,
            zipf=word.zipf,
            content=word.content,
            level=word.level,
            newness=knowledge_base.newness(word),
        )
        for position, word in enumerate(phrase.words)
        if position not in target
    )


def newness_of(rows: Iterable[PhraseWordRow]) -> PhraseNewness:
    """The newness of a phrase's other words, from their rows in any order."""
    return PhraseNewness.of(
        (row.lemma, row.zipf, row.newness) for row in sorted(rows, key=lambda r: r.position)
    )


def changes_at(lemma: LemmaKnowledge, now: datetime) -> datetime | None:
    """When the lemma's Anki timer makes it Known, if that is still ahead of `now`."""
    known_on = lemma.timer_known_on
    return known_on if known_on is not None and known_on > now else None
