"""Integration test: DB roundtrip + domain sorting."""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.application.utils.review_cards import ReviewCards
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.candidate_sorting import sort_by_relevance, sort_chronologically
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY
from backend.domain.value_objects.word_status import WordStatus
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)

from tests.decision_support import Decisions
from tests.phrase_support import phrase
from tests.word_support import CardSeed, store_cards

if TYPE_CHECKING:
    from backend.domain.value_objects.review_card import ReviewCard
    from sqlalchemy.orm import Session

KNOWLEDGE = UserKnowledge(EMPTY_VOCABULARY, CEFRLevel.B1, frequent_zipf=4.5)


def _make_candidate(
    source_id: int,
    lemma: str,
    zipf: float,
    *,
    cefr: str = "B1",
    occurrences: int = 1,
    is_phrasal_verb: bool = False,
    context_fragment: str = "",
    unknowns: int = 0,
    position: DocumentPosition | None = None,
) -> CardSeed:
    strange = [f"strange{i}" for i in range(unknowns)]
    return CardSeed(
        StoredCandidate(
            source_id=source_id,
            lemma=lemma,
            pos="NN",
            cefr_level=cefr,
            zipf_frequency=zipf,
            occurrences=occurrences,
            status=WordStatus.NEW,
            is_phrasal_verb=is_phrasal_verb,
        ),
        phrase(
            " ".join([context_fragment or f"context for {lemma}", *strange]), lemma, new=strange,
        ),
        position=position,
    )


def _cards(session: Session) -> list[ReviewCard]:
    elsewhere = MagicMock()
    elsewhere.of_lemmas.return_value = {}
    decisions = Decisions(session)
    return ReviewCards(
        SqlaCandidateRepository(session), SqlaOccurrenceRepository(session), elsewhere,
        decisions.word_states, decisions.vocabulary,
    ).of_source(1)


@pytest.fixture(autouse=True)
def _existing_source(source_id: int) -> int:
    return source_id


@pytest.mark.integration
class TestSortingWithDb:
    """Verify that candidates survive DB roundtrip and sort correctly."""

    def test_relevance_sort_after_db_roundtrip(self, db_session: Session) -> None:
        store_cards(db_session, [
            _make_candidate(1, "dirty_word", 4.0, unknowns=2),
            _make_candidate(1, "rare_word", 2.0, cefr="C1"),
            _make_candidate(1, "common_word", 5.0, cefr="A2"),
            _make_candidate(1, "mid_phrasal", 4.0, is_phrasal_verb=True),
            _make_candidate(1, "mid_regular", 4.0, cefr="B1"),
        ])
        sorted_candidates = sort_by_relevance(_cards(db_session), knowledge=KNOWLEDGE)
        assert [c.lemma for c in sorted_candidates] == [
            "common_word", "mid_regular", "rare_word", "mid_phrasal", "dirty_word",
        ]
        dirty = sorted_candidates[-1]
        assert dirty.phrase == _make_candidate(1, "dirty_word", 4.0, unknowns=2).text

    def test_chronological_sort_after_db_roundtrip(self, db_session: Session) -> None:
        store_cards(db_session, [
            _make_candidate(1, "third", 4.0, position=DocumentPosition(2, 0, 0, 0, 5)),
            _make_candidate(1, "first", 4.0, position=DocumentPosition(0, 1, 4, 1, 9)),
            _make_candidate(1, "second", 4.0, position=DocumentPosition(0, 2, 0, 2, 5)),
        ])
        sorted_candidates = sort_chronologically(_cards(db_session))
        assert [c.lemma for c in sorted_candidates] == ["first", "second", "third"]

    def test_is_sweet_spot_computed_after_load(self, db_session: Session) -> None:
        """is_sweet_spot is computed from zipf, not read from DB column."""
        repo = SqlaCandidateRepository(db_session)
        store_cards(db_session, [
            _make_candidate(1, "mid_word", 4.0),      # MID -> sweet spot
            _make_candidate(1, "common_word", 5.0),    # COMMON -> not sweet spot
        ])
        loaded = repo.get_by_source(1)
        by_lemma = {c.lemma: c for c in loaded}
        assert by_lemma["mid_word"].is_sweet_spot is True
        assert by_lemma["common_word"].is_sweet_spot is False
