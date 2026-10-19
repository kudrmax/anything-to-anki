"""Card phrases for tests, without a parser.

Every word is its own lowercase lemma, easy and frequent, so no word of a phrase is new
unless a test says which are (`new`). The target is the given words in order — by
dictionary form or as written — or the first word.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.entities.occurrence import Occurrence
from backend.domain.services.phrase_building import (
    TokenFacts,
    target_by_lemma,
    word_spans,
    words_of,
)
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.phrase import Phrase
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.infrastructure.persistence.models import PhraseModel, load_phrase

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.orm import Session

EASY_ZIPF = 6.0
RARE_ZIPF = 2.5


def phrase(
    text: str,
    target: str | None = None,
    *,
    new: Iterable[str] = (),
    lemmas: dict[str, str] | None = None,
) -> Phrase:
    """`new`: words that are rare and above any level; `lemmas`: word → its dictionary form."""
    rare = {word.lower() for word in new}
    forms = {k.lower(): v for k, v in (lemmas or {}).items()}
    facts = [
        TokenFacts(
            start=start, end=end,
            lemma=forms.get(text[start:end].lower(), text[start:end].lower()),
            level=CEFRLevel.C2 if text[start:end].lower() in rare else CEFRLevel.A1,
            zipf=RARE_ZIPF if text[start:end].lower() in rare else EASY_ZIPF,
            content=text[start:end].lower() in rare,
            alpha=True,
        )
        for start, end in word_spans(text)
    ]
    words = words_of(text, facts)
    found = target_by_lemma(words, text, target) if target else ()
    return Phrase(text=text, words=words, target=found or (0,))


def make_occurrence(
    source_text: str = "He glared at me.",
    *,
    polished_text: str | None = None,
    meaning_text: str | None = None,
    candidate_id: int = 1,
    shown_by: ShownBy | None = None,
) -> Occurrence:
    """An occurrence with the given phrase text; the rest is changed with `replace`."""
    meaning = (
        CandidateMeaning(
            candidate_id=candidate_id, meaning=meaning_text, translation=None,
            synonyms=None, examples=None, ipa=None, generated_at=None,
        )
        if meaning_text is not None
        else None
    )
    return Occurrence(
        candidate_id=candidate_id,
        origin=OccurrenceOrigin.AUTO,
        source_phrase=phrase(source_text),
        phrase_position=None,
        key=None,
        fragment_score=None, earned_section=CandidateSection.READY,
        shown_by=shown_by,
        polished_phrase=phrase(polished_text) if polished_text is not None else None,
        meaning=meaning,
    )


def shown_lemmas(session: Session, phrase_id: int) -> set[str]:
    """The lowercase lemmas of the stored phrase a card shows."""
    session.expire_all()
    model = session.get(PhraseModel, phrase_id)
    assert model is not None
    shown = load_phrase(model.shown_text)
    assert shown is not None
    return {word.lemma.lower() for word in shown.words}
