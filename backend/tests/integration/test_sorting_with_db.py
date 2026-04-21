"""Integration test: DB roundtrip + domain sorting."""
from __future__ import annotations

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.candidate_sorting import sort_by_relevance, sort_chronologically
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from sqlalchemy.orm import Session


def _make_candidate(
    source_id: int,
    lemma: str,
    zipf: float,
    *,
    cefr: str = "B1",
    occurrences: int = 1,
    is_phrasal_verb: bool = False,
    context_fragment: str = "",
) -> StoredCandidate:
    return StoredCandidate(
        source_id=source_id,
        lemma=lemma,
        pos="NN",
        cefr_level=cefr,
        zipf_frequency=zipf,
        context_fragment=context_fragment or f"context for {lemma}",
        fragment_purity="clean",
        occurrences=occurrences,
        status=CandidateStatus.PENDING,
        is_phrasal_verb=is_phrasal_verb,
    )


@pytest.mark.integration
class TestSortingWithDb:
    """Verify that candidates survive DB roundtrip and sort correctly."""

    def test_relevance_sort_after_db_roundtrip(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        repo.create_batch([
            _make_candidate(1, "rare_word", 2.0, cefr="C1"),
            _make_candidate(1, "common_word", 5.0, cefr="A2"),
            _make_candidate(1, "mid_phrasal", 4.0, is_phrasal_verb=True),
            _make_candidate(1, "mid_regular", 4.0, cefr="B1"),
        ])
        loaded = repo.get_by_source(1)
        sorted_candidates = sort_by_relevance(loaded)
        lemmas = [c.lemma for c in sorted_candidates]
        # COMMON(5.0) > MID (phrasal interleaved, not grouped) > RARE
        assert lemmas.index("common_word") == 0
        assert lemmas.index("rare_word") == len(lemmas) - 1
        assert "mid_phrasal" in lemmas
        assert "mid_regular" in lemmas

    def test_chronological_sort_after_db_roundtrip(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        repo.create_batch([
            _make_candidate(1, "third", 4.0, context_fragment="third thing"),
            _make_candidate(1, "first", 4.0, context_fragment="first thing"),
            _make_candidate(1, "second", 4.0, context_fragment="second thing"),
        ])
        loaded = repo.get_by_source(1)
        text = "the first thing then second thing finally third thing"
        sorted_candidates = sort_chronologically(loaded, source_text=text)
        assert [c.lemma for c in sorted_candidates] == ["first", "second", "third"]

    def test_is_sweet_spot_computed_after_load(self, db_session: Session) -> None:
        """is_sweet_spot is computed from zipf, not read from DB column."""
        repo = SqlaCandidateRepository(db_session)
        repo.create_batch([
            _make_candidate(1, "mid_word", 4.0),      # MID -> sweet spot
            _make_candidate(1, "common_word", 5.0),    # COMMON -> not sweet spot
        ])
        loaded = repo.get_by_source(1)
        by_lemma = {c.lemma: c for c in loaded}
        assert by_lemma["mid_word"].is_sweet_spot is True
        assert by_lemma["common_word"].is_sweet_spot is False
