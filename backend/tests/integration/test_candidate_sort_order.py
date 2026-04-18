"""Integration tests for candidate sort order (RELEVANCE and CHRONOLOGICAL)."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)


def _make_candidate(
    source_id: int,
    lemma: str,
    cefr_level: str,
    zipf_frequency: float,
    is_sweet_spot: bool = False,
) -> StoredCandidate:
    return StoredCandidate(
        source_id=source_id,
        lemma=lemma,
        pos="NN",
        cefr_level=cefr_level,
        zipf_frequency=zipf_frequency,
        is_sweet_spot=is_sweet_spot,
        context_fragment=f"context for {lemma}",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.PENDING,
    )


@pytest.mark.integration
class TestCandidateSortRelevance:
    """RELEVANCE: sweet-spot first, then zipf desc, then CEFR asc."""

    def test_sweet_spot_first(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        repo.create_batch([
            _make_candidate(1, "normal", "B1", 4.0, is_sweet_spot=False),
            _make_candidate(1, "sweet", "B1", 4.0, is_sweet_spot=True),
        ])
        results = repo.get_by_source(1, sort_order=CandidateSortOrder.RELEVANCE)
        assert results[0].lemma == "sweet"
        assert results[1].lemma == "normal"

    def test_higher_frequency_first(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        repo.create_batch([
            _make_candidate(1, "rare", "B1", 2.0),
            _make_candidate(1, "common", "B1", 5.0),
        ])
        results = repo.get_by_source(1, sort_order=CandidateSortOrder.RELEVANCE)
        assert results[0].lemma == "common"
        assert results[1].lemma == "rare"

    def test_lower_cefr_first(self, db_session: Session) -> None:
        """At same frequency, easier (lower CEFR) words come first."""
        repo = SqlaCandidateRepository(db_session)
        repo.create_batch([
            _make_candidate(1, "hard", "C2", 4.0),
            _make_candidate(1, "medium", "B1", 4.0),
            _make_candidate(1, "easy", "A2", 4.0),
        ])
        results = repo.get_by_source(1, sort_order=CandidateSortOrder.RELEVANCE)
        assert [r.lemma for r in results] == ["easy", "medium", "hard"]

    def test_full_priority_order(self, db_session: Session) -> None:
        """Sweet-spot > frequency > CEFR level (asc)."""
        repo = SqlaCandidateRepository(db_session)
        repo.create_batch([
            _make_candidate(1, "c2_rare", "C2", 2.0),
            _make_candidate(1, "b1_common", "B1", 5.0),
            _make_candidate(1, "a2_sweet", "A2", 3.0, is_sweet_spot=True),
            _make_candidate(1, "b2_common", "B2", 5.0),
        ])
        results = repo.get_by_source(1, sort_order=CandidateSortOrder.RELEVANCE)
        lemmas = [r.lemma for r in results]
        # sweet-spot first, then same-freq sorted by cefr asc, then rare
        assert lemmas == ["a2_sweet", "b1_common", "b2_common", "c2_rare"]


@pytest.mark.integration
class TestCandidateSortChronological:
    """CHRONOLOGICAL: insertion order (id asc)."""

    def test_insertion_order(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        repo.create_batch([
            _make_candidate(1, "first", "C2", 2.0),
            _make_candidate(1, "second", "A1", 5.0),
            _make_candidate(1, "third", "B1", 3.0),
        ])
        results = repo.get_by_source(1, sort_order=CandidateSortOrder.CHRONOLOGICAL)
        assert [r.lemma for r in results] == ["first", "second", "third"]
