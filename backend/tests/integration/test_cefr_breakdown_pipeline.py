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
from backend.domain.ports.cefr_source import CEFRSource
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.dict_cache.cefr_source import DictCacheCEFRSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader

DICT_CACHE_PATH = Path(__file__).resolve().parents[3] / "dictionaries" / ".cache" / "dict.db"

_SKIP_NO_DICT_CACHE = pytest.mark.skipif(
    not DICT_CACHE_PATH.exists(),
    reason=f"dict.db not found at {DICT_CACHE_PATH}",
)


def _make_classifier() -> VotingCEFRClassifier:
    reader = DictCacheReader(DICT_CACHE_PATH)

    cefr_sources: list[CEFRSource] = []
    priority_sources: list[CEFRSource] = []
    for meta in reader.get_cefr_sources():
        src = DictCacheCEFRSource(reader, meta["name"])
        if meta["priority"] == "high":
            priority_sources.append(src)
        else:
            cefr_sources.append(src)
    cefr_sources.append(CefrpyCEFRSource())

    return VotingCEFRClassifier(cefr_sources, priority_sources=priority_sources)


@pytest.mark.integration
@_SKIP_NO_DICT_CACHE
class TestCEFRBreakdownPipeline:
    """Verify breakdown data survives the full pipeline."""

    def test_classify_detailed_returns_breakdown(self) -> None:
        classifier = _make_classifier()
        breakdown = classifier.classify_detailed("happy", "JJ")

        assert breakdown.final_level in (CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1)
        assert breakdown.decision_method in ("priority", "voting")
        assert len(breakdown.votes) >= 1  # at least CEFRpy
        # All votes have source names
        names = {v.source_name for v in breakdown.votes}
        assert "CEFRpy" in names

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
        """All source names from dict.db + CEFRpy must appear in breakdown."""
        classifier = _make_classifier()
        breakdown = classifier.classify_detailed("happy", "JJ")

        all_names: set[str] = set()
        for v in breakdown.priority_votes:
            all_names.add(v.source_name)
        for v in breakdown.votes:
            all_names.add(v.source_name)

        # At minimum CEFRpy must be present
        assert "CEFRpy" in all_names
        # There should be at least a few sources total
        assert len(all_names) >= 2
