"""Phrases collected for a topic or the saved phrases: shown phrases of their words."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.utils.collected_phrases import CollectedPhrases
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.new_card import NewCard
from backend.domain.value_objects.phrase_origin import PhraseOrigin
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


def _card(source_id: int, lemma: str, text: str, origin: PhraseOrigin | None = None) -> NewCard:
    return NewCard(
        word=StoredCandidate(
            source_id=source_id, lemma=lemma, pos="VERB", cefr_level="B2", zipf_frequency=3.0,
            occurrences=1, status=WordStatus.NEW,
        ),
        phrase=phrase(text, lemma.lower()),
        origin=origin,
    )


def _collected(session: Session) -> CollectedPhrases:
    return CollectedPhrases(SqlaCandidateRepository(session), SqlaOccurrenceRepository(session))


def test_a_collected_phrase_is_a_shown_phrase_of_a_new_word(
    db_session: Session, source_id: int,
) -> None:
    [collected] = _collected(db_session).add(
        source_id, [_card(source_id, "glare", "he glare at me", PhraseOrigin.generated())],
    )

    added = SqlaOccurrenceRepository(db_session).get(collected.phrase_id)
    assert added is not None
    assert (added.origin, added.shown_by) == (OccurrenceOrigin.COLLECTED, ShownBy.USER)
    assert added.collected_from == PhraseOrigin.generated()
    assert added.source_phrase.text == "he glare at me"
    assert not added.card_state.is_decision
    word = SqlaCandidateRepository(db_session).get_by_id(added.candidate_id)
    assert word is not None
    assert (word.lemma, word.status) == ("glare", WordStatus.NEW)


def test_a_phrase_of_a_word_the_source_has_joins_that_word(
    db_session: Session, source_id: int,
) -> None:
    collected = _collected(db_session)
    [first] = collected.add(source_id, [_card(source_id, "glare", "he glare at me")])

    [second] = collected.add(source_id, [_card(source_id, "Glare", "they glare")])

    occurrences = SqlaOccurrenceRepository(db_session)
    first_phrase = occurrences.get(first.phrase_id)
    second_phrase = occurrences.get(second.phrase_id)
    assert first_phrase is not None
    assert second_phrase is not None
    assert first_phrase.candidate_id == second_phrase.candidate_id
    assert len(SqlaCandidateRepository(db_session).get_by_source(source_id)) == 1


def test_a_collected_phrase_says_whether_its_word_is_new(
    db_session: Session, source_id: int,
) -> None:
    collected = _collected(db_session)
    [first] = collected.add(source_id, [_card(source_id, "glare", "he glare at me")])

    [second] = collected.add(source_id, [_card(source_id, "glare", "they glare")])

    assert (first.new_word, second.new_word) == (True, False)


def test_a_collected_phrase_is_no_decision(db_session: Session, source_id: int) -> None:
    collected = _collected(db_session)
    collected.add(source_id, [_card(source_id, "glare", "he glare at me")])
    collected.add(source_id, [_card(source_id, "linger", "we linger")])

    words = SqlaCandidateRepository(db_session)
    assert words.count_by_status(WordStatus.NEW) == 2  # noqa: PLR2004 — both words
    assert words.get_all_by_status(WordStatus.LEARN) == []
