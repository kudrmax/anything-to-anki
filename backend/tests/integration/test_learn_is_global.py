"""Q12: a Learn not exported yet is global. Once a word is marked Learn in one source, its
cards in another source are done, labelled "Learn in another source"; calibration and the
analysis of a new source skip the word. All of it read from the request's one snapshot."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.dto.source_dtos import card_to_dto
from backend.application.use_cases.get_bootstrap_words import GetBootstrapWordsUseCase
from backend.application.utils.review_cards import ReviewCards
from backend.application.utils.word_knowledge import WordKnowledge
from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.services.card_view import section
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.card_note import CardNote
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)

from tests.decision_support import Decisions
from tests.integration.conftest import insert_source
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from backend.domain.value_objects.review_card import ReviewCard
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration

HERE, THERE = 1, 2
GLARE, GLARE_THERE = 1, 2
LEMMA = "glare"


@pytest.fixture
def decisions(db_session: Session) -> Decisions:
    insert_source(db_session, HERE)
    insert_source(db_session, THERE)
    insert_word(db_session, GLARE, source_id=HERE, lemma=LEMMA)
    insert_word(db_session, GLARE_THERE, source_id=THERE, lemma=LEMMA)
    first = Decisions(db_session)
    first.decide_phrase().press(phrase_id_of(GLARE), Press.LEARN)
    return first.request()


def _card_there(decisions: Decisions) -> ReviewCard:
    session = decisions.session
    [card] = ReviewCards(
        SqlaCandidateRepository(session), SqlaOccurrenceRepository(session),
        decisions.word_states, decisions.vocabulary,
    ).of_source(THERE)
    return card


def test_the_cards_in_another_source_are_done_as_learn_elsewhere(decisions: Decisions) -> None:
    card = _card_there(decisions)

    assert card.elsewhere is ElsewhereStatus.LEARN
    assert card.view.note is CardNote.LEARN_ELSEWHERE
    assert card.view.shown.status is WordStatus.LEARN
    assert section(card.view, CandidateSection.READY) is CandidateSection.REVIEWED
    state = card_to_dto(card).state
    assert (state.elsewhere, state.note) == (ElsewhereStatus.LEARN, CardNote.LEARN_ELSEWHERE)


def test_calibration_skips_the_word(decisions: Decisions) -> None:
    index = MagicMock()
    index.get_all_entries.return_value = [
        BootstrapWordEntry(LEMMA, CEFRLevel.B2, 3.2),
        BootstrapWordEntry("drift", CEFRLevel.B2, 4.2),
    ]
    settings = MagicMock()
    settings.get.return_value = "B1"

    offered = GetBootstrapWordsUseCase(index, decisions.vocabulary, settings).execute([])

    assert [word.lemma for word in offered] == ["drift"]


def test_a_new_source_does_not_offer_the_word(decisions: Decisions) -> None:
    knowledge = WordKnowledge(
        MagicMock(), MagicMock(), CEFRLevel.B1, decisions.vocabulary.snapshot(), None,
    )

    assert knowledge.is_known_or_learning(LEMMA)
    assert not knowledge.is_known_or_learning("drift")
