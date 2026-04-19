"""Unit tests: CEFR breakdown propagation through _to_dto functions.

Covers bugs #1-3: breakdown was silently dropped in get_sources, get_candidates,
and add_manual_candidate because _to_dto functions didn't include cefr_breakdown.
"""
from __future__ import annotations

from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_level import CEFRLevel


def _make_breakdown() -> CEFRBreakdown:
    return CEFRBreakdown(
        final_level=CEFRLevel.B1,
        decision_method="priority",
        priority_vote=SourceVote(
            source_name="Cambridge Dictionary",
            distribution={CEFRLevel.B1: 1.0},
            top_level=CEFRLevel.B1,
        ),
        votes=[
            SourceVote(source_name="CEFRpy", distribution={CEFRLevel.B1: 1.0}, top_level=CEFRLevel.B1),
            SourceVote(source_name="EFLLex", distribution={CEFRLevel.A2: 0.6, CEFRLevel.B1: 0.4}, top_level=CEFRLevel.A2),
            SourceVote(source_name="Oxford 5000", distribution={CEFRLevel.UNKNOWN: 1.0}, top_level=CEFRLevel.UNKNOWN),
            SourceVote(source_name="Kelly List", distribution={CEFRLevel.UNKNOWN: 1.0}, top_level=CEFRLevel.UNKNOWN),
        ],
    )


def _make_stored_candidate(with_breakdown: bool = True) -> StoredCandidate:
    return StoredCandidate(
        id=1,
        source_id=1,
        lemma="happy",
        pos="JJ",
        cefr_level="B1",
        zipf_frequency=5.0,
        is_sweet_spot=True,
        context_fragment="I am happy",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.PENDING,
        cefr_breakdown=_make_breakdown() if with_breakdown else None,
    )


class TestGetSourcesCandidateToDto:
    """get_sources._candidate_to_dto must include breakdown."""

    def test_breakdown_included(self) -> None:
        from backend.application.use_cases.get_sources import _candidate_to_dto

        candidate = _make_stored_candidate(with_breakdown=True)
        dto = _candidate_to_dto(candidate)

        assert dto.cefr_breakdown is not None
        assert dto.cefr_breakdown.decision_method == "priority"
        assert dto.cefr_breakdown.priority_vote is not None
        assert dto.cefr_breakdown.priority_vote.source_name == "Cambridge Dictionary"
        assert len(dto.cefr_breakdown.votes) == 4

    def test_no_breakdown_is_none(self) -> None:
        from backend.application.use_cases.get_sources import _candidate_to_dto

        candidate = _make_stored_candidate(with_breakdown=False)
        dto = _candidate_to_dto(candidate)

        assert dto.cefr_breakdown is None


class TestGetCandidatesToDto:
    """get_candidates._to_dto must include breakdown."""

    def test_breakdown_included(self) -> None:
        from backend.application.use_cases.get_candidates import _to_dto

        candidate = _make_stored_candidate(with_breakdown=True)
        dto = _to_dto(candidate)

        assert dto.cefr_breakdown is not None
        assert dto.cefr_breakdown.decision_method == "priority"
        assert len(dto.cefr_breakdown.votes) == 4

    def test_no_breakdown_is_none(self) -> None:
        from backend.application.use_cases.get_candidates import _to_dto

        candidate = _make_stored_candidate(with_breakdown=False)
        dto = _to_dto(candidate)

        assert dto.cefr_breakdown is None


class TestEFLLexDistributionInDto:
    """EFLLex distribution must survive conversion to DTO."""

    def test_efllex_has_distribution(self) -> None:
        from backend.application.use_cases.get_sources import _candidate_to_dto

        candidate = _make_stored_candidate(with_breakdown=True)
        dto = _candidate_to_dto(candidate)

        assert dto.cefr_breakdown is not None
        efllex_vote = next(v for v in dto.cefr_breakdown.votes if v.source_name == "EFLLex")
        assert efllex_vote.distribution is not None
        assert "A2" in efllex_vote.distribution
        assert "B1" in efllex_vote.distribution

    def test_non_efllex_has_no_distribution(self) -> None:
        from backend.application.use_cases.get_sources import _candidate_to_dto

        candidate = _make_stored_candidate(with_breakdown=True)
        dto = _candidate_to_dto(candidate)

        assert dto.cefr_breakdown is not None
        cefrpy_vote = next(v for v in dto.cefr_breakdown.votes if v.source_name == "CEFRpy")
        assert cefrpy_vote.distribution is None


class TestProcessSourceBreakdownPropagation:
    """process_source must pass breakdown from WordCandidateDTO to StoredCandidate."""

    def test_dto_to_breakdown_roundtrip(self) -> None:
        """Simulates what process_source does: DTO → domain → StoredCandidate."""
        from backend.application.dto.cefr_dtos import breakdown_to_dto, dto_to_breakdown

        original = _make_breakdown()

        # analyze_text converts domain → DTO
        dto = breakdown_to_dto(original)
        assert dto.decision_method == "priority"

        # process_source converts DTO → domain for StoredCandidate
        restored = dto_to_breakdown(dto)
        assert restored.decision_method == original.decision_method
        assert restored.final_level == original.final_level
        assert len(restored.votes) == len(original.votes)
