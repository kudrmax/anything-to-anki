"""Unit tests: CEFR breakdown propagation through _to_dto functions.

Covers bugs #1-3: breakdown was silently dropped in get_sources, get_candidates,
and add_manual_candidate because _to_dto functions didn't include cefr_breakdown.
"""
from __future__ import annotations

from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel


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
            SourceVote(source_name="EFLLex", distribution={CEFRLevel.A2: 0.6, CEFRLevel.B1: 0.4}, top_level=CEFRLevel.A2),
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
        context_fragment="I am happy",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.PENDING,
        cefr_breakdown=_make_breakdown() if with_breakdown else None,
    )


class TestStoredCandidateToDto:
    """stored_candidate_to_dto must include CEFR breakdown."""

    def test_breakdown_included(self) -> None:
        from backend.application.dto.source_dtos import stored_candidate_to_dto

        candidate = _make_stored_candidate(with_breakdown=True)
        dto = stored_candidate_to_dto(candidate)

        assert dto.cefr_breakdown is not None
        assert dto.cefr_breakdown.decision_method == "priority"
        assert len(dto.cefr_breakdown.priority_votes) == 2
        assert dto.cefr_breakdown.priority_votes[1].source_name == "Cambridge Dictionary"
        assert len(dto.cefr_breakdown.votes) == 3

    def test_no_breakdown_is_none(self) -> None:
        from backend.application.dto.source_dtos import stored_candidate_to_dto

        candidate = _make_stored_candidate(with_breakdown=False)
        dto = stored_candidate_to_dto(candidate)

        assert dto.cefr_breakdown is None

    def test_efllex_has_distribution(self) -> None:
        from backend.application.dto.source_dtos import stored_candidate_to_dto

        candidate = _make_stored_candidate(with_breakdown=True)
        dto = stored_candidate_to_dto(candidate)

        assert dto.cefr_breakdown is not None
        efllex_vote = next(v for v in dto.cefr_breakdown.votes if v.source_name == "EFLLex")
        assert efllex_vote.distribution is not None
        assert "A2" in efllex_vote.distribution
        assert "B1" in efllex_vote.distribution

    def test_non_efllex_has_no_distribution(self) -> None:
        from backend.application.dto.source_dtos import stored_candidate_to_dto

        candidate = _make_stored_candidate(with_breakdown=True)
        dto = stored_candidate_to_dto(candidate)

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

    def test_dto_to_breakdown_uses_runtime_resolver(self) -> None:
        """dto_to_breakdown must compute level via resolve_cefr_level, not trust DTO fields."""
        from backend.application.dto.cefr_dtos import dto_to_breakdown
        from backend.application.dto.cefr_dtos import CEFRBreakdownDTO, SourceVoteDTO

        # DTO says "voting" but Oxford knows the word → resolver should say "priority"
        dto = CEFRBreakdownDTO(
            decision_method="voting",  # stale/wrong
            priority_votes=[
                SourceVoteDTO(source_name="Oxford 5000", level="B2"),
                SourceVoteDTO(source_name="Cambridge Dictionary", level=None),
            ],
            votes=[
                SourceVoteDTO(source_name="CEFRpy", level="C1"),
            ],
        )
        restored = dto_to_breakdown(dto)
        # Resolver sees Oxford B2 → priority, ignoring the stale "voting"
        assert restored.final_level == CEFRLevel.B2
        assert restored.decision_method == "priority"
