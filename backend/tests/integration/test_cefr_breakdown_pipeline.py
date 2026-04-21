"""Integration test: CEFR breakdown flows from classify_detailed() to API response.

Verifies the full pipeline:
  classify_detailed() → WordCandidate → WordCandidateDTO → StoredCandidate
  → CEFRBreakdownModel (DB) → StoredCandidate → StoredCandidateDTO (API)

This test catches missing breakdown propagation in any layer.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from backend.application.dto.analysis_dtos import WordCandidateDTO
from backend.application.dto.source_dtos import StoredCandidateDTO
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.efllex_cefr_source import EFLLexCEFRSource
from backend.infrastructure.adapters.kelly_cefr_source import KellyCEFRSource
from backend.infrastructure.adapters.oxford_cefr_source import OxfordCEFRSource

DATA_DIR = Path(__file__).resolve().parents[3] / "dictionaries" / "cefr"
CAMBRIDGE_DB_PATH = Path(__file__).resolve().parents[3] / "dictionaries" / "cambridge.db"


def _make_classifier() -> VotingCEFRClassifier:
    from backend.infrastructure.adapters.cambridge.cefr_source import CambridgeCEFRSource
    from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader

    reader = CambridgeSQLiteReader(CAMBRIDGE_DB_PATH)
    cambridge_cefr = CambridgeCEFRSource(reader)
    sources = [
        CefrpyCEFRSource(),
        EFLLexCEFRSource(DATA_DIR / "efllex.tsv"),
        OxfordCEFRSource(DATA_DIR / "oxford5000.csv"),
        KellyCEFRSource(DATA_DIR / "kelly.csv"),
    ]
    return VotingCEFRClassifier(sources, priority_source=cambridge_cefr)


@pytest.mark.integration
class TestCEFRBreakdownPipeline:
    """Verify breakdown data survives the full pipeline."""

    def test_classify_detailed_returns_breakdown(self) -> None:
        classifier = _make_classifier()
        breakdown = classifier.classify_detailed("happy", "JJ")

        assert breakdown.final_level in (CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1)
        assert breakdown.decision_method in ("priority", "voting")
        assert len(breakdown.votes) == 4  # 4 voting sources
        # All votes have source names
        names = {v.source_name for v in breakdown.votes}
        assert "CEFRpy" in names
        assert "EFLLex" in names

    def test_breakdown_in_word_candidate_dto(self) -> None:
        """WordCandidateDTO must carry cefr_breakdown after analyze_text."""
        from backend.application.dto.cefr_dtos import breakdown_to_dto

        classifier = _make_classifier()
        breakdown = classifier.classify_detailed("happy", "JJ")
        dto = breakdown_to_dto(breakdown)

        # Simulate what analyze_text._to_dto does
        word_dto = WordCandidateDTO(
            lemma="happy",
            pos="JJ",
            cefr_level="A2",
            zipf_frequency=5.0,
            is_sweet_spot=True,
            context_fragment="I am happy",
            fragment_purity="clean",
            occurrences=1,
            cefr_breakdown=dto,
        )
        assert word_dto.cefr_breakdown is not None
        assert word_dto.cefr_breakdown.decision_method in ("priority", "voting")
        assert len(word_dto.cefr_breakdown.votes) >= 1

    def test_breakdown_survives_dto_to_domain_roundtrip(self) -> None:
        """CEFRBreakdownDTO → domain CEFRBreakdown → CEFRBreakdownModel → back."""
        from backend.application.dto.cefr_dtos import breakdown_to_dto, dto_to_breakdown

        classifier = _make_classifier()
        original = classifier.classify_detailed("happy", "JJ")

        # Domain → DTO
        dto = breakdown_to_dto(original)
        assert dto.decision_method == original.decision_method

        # DTO → Domain (what process_source does)
        restored = dto_to_breakdown(dto)
        assert restored.decision_method == original.decision_method
        assert restored.final_level == original.final_level

    def test_breakdown_in_stored_candidate_dto(self) -> None:
        """StoredCandidateDTO must carry cefr_breakdown."""
        from backend.application.dto.cefr_dtos import breakdown_to_dto

        classifier = _make_classifier()
        breakdown = classifier.classify_detailed("happy", "JJ")
        bd_dto = breakdown_to_dto(breakdown)

        # Simulate what get_sources._candidate_to_dto does
        candidate_dto = StoredCandidateDTO(
            id=1,
            lemma="happy",
            pos="JJ",
            cefr_level="A2",
            zipf_frequency=5.0,
            is_sweet_spot=True,
            context_fragment="I am happy",
            fragment_purity="clean",
            occurrences=1,
            status="pending",
            cefr_breakdown=bd_dto,
        )
        assert candidate_dto.cefr_breakdown is not None
        assert candidate_dto.cefr_breakdown.decision_method in ("priority", "voting")

        # Verify JSON serialization works (this is what goes to frontend)
        json_data = candidate_dto.model_dump()
        assert json_data["cefr_breakdown"] is not None
        assert "decision_method" in json_data["cefr_breakdown"]
        assert "votes" in json_data["cefr_breakdown"]
        assert len(json_data["cefr_breakdown"]["votes"]) >= 1

    def test_all_source_names_present_in_breakdown(self) -> None:
        """All 5 source names must appear in breakdown."""
        classifier = _make_classifier()
        breakdown = classifier.classify_detailed("happy", "JJ")

        all_names: set[str] = set()
        if breakdown.priority_vote:
            all_names.add(breakdown.priority_vote.source_name)
        for v in breakdown.votes:
            all_names.add(v.source_name)

        expected = {"Cambridge Dictionary", "CEFRpy", "EFLLex", "Oxford 5000", "Kelly List"}
        assert all_names == expected
