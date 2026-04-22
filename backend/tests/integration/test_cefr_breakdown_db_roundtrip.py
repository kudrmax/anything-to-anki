"""Integration test: CEFR breakdown survives DB roundtrip.

StoredCandidate with breakdown → StoredCandidateModel (DB) → StoredCandidate → DTO
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)


def _make_breakdown() -> CEFRBreakdown:
    return CEFRBreakdown(
        final_level=CEFRLevel.B1,
        decision_method="priority",
        priority_votes=[
            SourceVote(
                source_name="Oxford 5000",
                distribution={CEFRLevel.UNKNOWN: 1.0},
                top_level=CEFRLevel.UNKNOWN,
            ),
            SourceVote(
                source_name="Cambridge Dictionary",
                distribution={CEFRLevel.B1: 1.0},
                top_level=CEFRLevel.B1,
            ),
        ],
        votes=[
            SourceVote(source_name="CEFRpy", distribution={CEFRLevel.B1: 1.0}, top_level=CEFRLevel.B1),
            SourceVote(
                source_name="EFLLex",
                distribution={CEFRLevel.A2: 0.6, CEFRLevel.B1: 0.3, CEFRLevel.B2: 0.1},
                top_level=CEFRLevel.A2,
            ),
            SourceVote(source_name="Kelly List", distribution={CEFRLevel.UNKNOWN: 1.0}, top_level=CEFRLevel.UNKNOWN),
        ],
    )


@pytest.mark.integration
class TestCEFRBreakdownDBRoundtrip:
    def test_breakdown_saved_and_loaded(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        candidate = StoredCandidate(
            source_id=1,
            lemma="happy",
            pos="JJ",
            cefr_level="B1",
            zipf_frequency=5.0,
            context_fragment="I am happy",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            cefr_breakdown=_make_breakdown(),
        )
        created = repo.create_batch([candidate])
        assert len(created) == 1

        loaded = repo.get_by_source(1)
        assert len(loaded) == 1
        c = loaded[0]

        assert c.cefr_breakdown is not None
        assert c.cefr_breakdown.decision_method == "priority"
        assert c.cefr_breakdown.final_level == CEFRLevel.B1

    def test_breakdown_priority_votes_restored(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        candidate = StoredCandidate(
            source_id=1,
            lemma="test",
            pos="NN",
            cefr_level="A2",
            zipf_frequency=4.0,
            context_fragment="a test",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            cefr_breakdown=_make_breakdown(),
        )
        repo.create_batch([candidate])

        loaded = repo.get_by_source(1)[0]
        assert loaded.cefr_breakdown is not None
        assert len(loaded.cefr_breakdown.priority_votes) == 2
        cambridge = next(
            v for v in loaded.cefr_breakdown.priority_votes
            if v.source_name == "Cambridge Dictionary"
        )
        assert cambridge.top_level == CEFRLevel.B1

    def test_voting_sources_restored(self, db_session: Session) -> None:
        repo = SqlaCandidateRepository(db_session)
        candidate = StoredCandidate(
            source_id=1,
            lemma="word",
            pos="NN",
            cefr_level="B1",
            zipf_frequency=4.0,
            context_fragment="a word",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            cefr_breakdown=_make_breakdown(),
        )
        repo.create_batch([candidate])

        loaded = repo.get_by_source(1)[0]
        bd = loaded.cefr_breakdown
        assert bd is not None

        names = {v.source_name for v in bd.votes}
        assert "CEFRpy" in names
        assert "EFLLex" in names
        assert "Kelly List" in names

    def test_efllex_distribution_survives_db(self, db_session: Session) -> None:
        """EFLLex distribution (JSON) must survive write → read."""
        repo = SqlaCandidateRepository(db_session)
        candidate = StoredCandidate(
            source_id=1,
            lemma="run",
            pos="VB",
            cefr_level="A2",
            zipf_frequency=5.5,
            context_fragment="run fast",
            fragment_purity="clean",
            occurrences=2,
            status=CandidateStatus.PENDING,
            cefr_breakdown=_make_breakdown(),
        )
        repo.create_batch([candidate])

        loaded = repo.get_by_source(1)[0]
        bd = loaded.cefr_breakdown
        assert bd is not None

        efllex = next(v for v in bd.votes if v.source_name == "EFLLex")
        assert CEFRLevel.A2 in efllex.distribution
        assert efllex.distribution[CEFRLevel.A2] == pytest.approx(0.6, abs=0.01)

    def test_no_breakdown_stays_none(self, db_session: Session) -> None:
        """Candidates without breakdown should have cefr_breakdown=None after load."""
        repo = SqlaCandidateRepository(db_session)
        candidate = StoredCandidate(
            source_id=1,
            lemma="old",
            pos="JJ",
            cefr_level="A1",
            zipf_frequency=5.0,
            context_fragment="old candidate",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            cefr_breakdown=None,
        )
        repo.create_batch([candidate])

        loaded = repo.get_by_source(1)[0]
        assert loaded.cefr_breakdown is None

    def test_breakdown_cascade_delete(self, db_session: Session) -> None:
        """Deleting candidate should cascade-delete breakdown."""
        from backend.infrastructure.persistence.models import CEFRBreakdownModel, StoredCandidateModel

        repo = SqlaCandidateRepository(db_session)
        candidate = StoredCandidate(
            source_id=1,
            lemma="gone",
            pos="VB",
            cefr_level="B2",
            zipf_frequency=4.0,
            context_fragment="it is gone",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            cefr_breakdown=_make_breakdown(),
        )
        created = repo.create_batch([candidate])
        cid = created[0].id

        # Verify breakdown exists
        assert db_session.query(CEFRBreakdownModel).filter_by(candidate_id=cid).one_or_none() is not None

        # Delete candidate directly
        model = db_session.get(StoredCandidateModel, cid)
        db_session.delete(model)
        db_session.flush()

        # Breakdown should be gone too
        assert db_session.query(CEFRBreakdownModel).filter_by(candidate_id=cid).one_or_none() is None

    def test_runtime_level_ignores_stored_cefr_level(self, db_session: Session) -> None:
        """cefr_level on loaded entity comes from runtime resolution, not DB column.

        We save cefr_level="C2" in the DB but the breakdown votes point to B1
        (Cambridge priority). After load, cefr_level must be B1 (runtime), not C2.
        """
        repo = SqlaCandidateRepository(db_session)
        candidate = StoredCandidate(
            source_id=1,
            lemma="mismatch",
            pos="NN",
            cefr_level="C2",  # deliberately wrong — should be overridden
            zipf_frequency=4.0,
            context_fragment="a mismatch",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            cefr_breakdown=_make_breakdown(),  # Cambridge knows B1
        )
        repo.create_batch([candidate])

        loaded = repo.get_by_source(1)[0]
        # Runtime resolver sees Cambridge=B1 → final_level=B1, NOT stored "C2"
        assert loaded.cefr_level == "B1"
        assert loaded.cefr_breakdown is not None
        assert loaded.cefr_breakdown.final_level == CEFRLevel.B1

    # fallback test removed: cefr_level column dropped, all candidates must have breakdown
