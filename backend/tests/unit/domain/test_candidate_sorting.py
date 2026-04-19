from __future__ import annotations

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.candidate_sorting import (
    sort_by_relevance,
    sort_chronologically,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.usage_distribution import UsageDistribution


def _make(
    lemma: str,
    zipf: float,
    *,
    cefr: str | None = "B1",
    occurrences: int = 1,
    is_phrasal_verb: bool = False,
    context_fragment: str = "",
    usage_distribution: UsageDistribution | None = None,
) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma=lemma,
        pos="NN",
        cefr_level=cefr,
        zipf_frequency=zipf,
        context_fragment=context_fragment or f"context for {lemma}",
        fragment_purity="clean",
        occurrences=occurrences,
        status=CandidateStatus.PENDING,
        is_phrasal_verb=is_phrasal_verb,
        usage_distribution=usage_distribution,
    )


@pytest.mark.unit
class TestSortByRelevance:
    def test_frequency_band_desc(self) -> None:
        """Higher frequency band (more common) comes first."""
        rare = _make("rare", 2.0)          # RARE
        common = _make("common", 5.0)      # COMMON
        result = sort_by_relevance([rare, common])
        assert [c.lemma for c in result] == ["common", "rare"]

    def test_phrasal_verb_within_same_band(self) -> None:
        """Phrasal verbs come before regular words within the same band."""
        regular = _make("walk", 4.0)
        phrasal = _make("give up", 4.0, is_phrasal_verb=True)
        result = sort_by_relevance([regular, phrasal])
        assert [c.lemma for c in result] == ["give up", "walk"]

    def test_band_beats_phrasal_verb(self) -> None:
        """A higher band wins over phrasal verb status."""
        phrasal_rare = _make("give up", 2.0, is_phrasal_verb=True)   # RARE
        regular_common = _make("explain", 5.0)                        # COMMON
        result = sort_by_relevance([phrasal_rare, regular_common])
        assert [c.lemma for c in result] == ["explain", "give up"]

    def test_cefr_asc_within_same_band(self) -> None:
        """Easier CEFR level first within the same band."""
        hard = _make("hard", 4.0, cefr="C2")
        easy = _make("easy", 4.0, cefr="A2")
        medium = _make("medium", 4.0, cefr="B1")
        result = sort_by_relevance([hard, easy, medium])
        assert [c.lemma for c in result] == ["easy", "medium", "hard"]

    def test_cefr_none_after_c2(self) -> None:
        """Candidates without CEFR go after C2."""
        no_cefr = _make("unknown", 4.0, cefr=None)
        c2 = _make("hard", 4.0, cefr="C2")
        a1 = _make("easy", 4.0, cefr="A1")
        result = sort_by_relevance([no_cefr, c2, a1])
        assert [c.lemma for c in result] == ["easy", "hard", "unknown"]

    def test_occurrences_desc(self) -> None:
        """More occurrences first within same band + cefr."""
        few = _make("few", 4.0, occurrences=1)
        many = _make("many", 4.0, occurrences=5)
        result = sort_by_relevance([few, many])
        assert [c.lemma for c in result] == ["many", "few"]

    def test_full_priority_order(self) -> None:
        """band DESC > phrasal DESC > cefr ASC > occurrences DESC."""
        candidates = [
            _make("rare_phrasal", 2.0, is_phrasal_verb=True),    # RARE, phrasal
            _make("common_a2", 5.0, cefr="A2"),                  # COMMON
            _make("mid_b1_many", 4.0, cefr="B1", occurrences=5), # MID
            _make("mid_b1_few", 4.0, cefr="B1", occurrences=1),  # MID
            _make("mid_a1", 4.0, cefr="A1"),                     # MID
        ]
        result = sort_by_relevance(candidates)
        assert [c.lemma for c in result] == [
            "common_a2",       # COMMON band (highest)
            "mid_a1",          # MID band, A1 (easiest cefr)
            "mid_b1_many",     # MID band, B1, 5 occurrences
            "mid_b1_few",      # MID band, B1, 1 occurrence
            "rare_phrasal",    # RARE band (lowest, phrasal irrelevant here)
        ]

    def test_empty_list(self) -> None:
        assert sort_by_relevance([]) == []

    def test_single_element(self) -> None:
        c = _make("only", 4.0)
        result = sort_by_relevance([c])
        assert len(result) == 1
        assert result[0].lemma == "only"

    def test_stable_sort(self) -> None:
        """Two candidates with identical sort keys preserve original order."""
        a = _make("alpha", 4.0)
        b = _make("beta", 4.0)
        result = sort_by_relevance([a, b])
        assert [c.lemma for c in result] == ["alpha", "beta"]
        # Reversed input → reversed output
        result2 = sort_by_relevance([b, a])
        assert [c.lemma for c in result2] == ["beta", "alpha"]

    def test_all_five_bands(self) -> None:
        """One candidate per band, verify order ULTRA_COMMON → COMMON → MID → LOW → RARE."""
        candidates = [
            _make("rare", 1.5),
            _make("low", 3.0),
            _make("mid", 4.0),
            _make("common", 5.0),
            _make("ultra", 6.0),
        ]
        result = sort_by_relevance(candidates)
        assert [c.lemma for c in result] == ["ultra", "common", "mid", "low", "rare"]


@pytest.mark.unit
class TestSortChronologically:
    def test_by_position_in_text(self) -> None:
        c1 = _make("first", 4.0, context_fragment="first word")
        c2 = _make("second", 4.0, context_fragment="second word")
        c3 = _make("third", 4.0, context_fragment="third word")
        text = "the first word then second word finally third word"
        result = sort_chronologically([c3, c1, c2], source_text=text)
        assert [c.lemma for c in result] == ["first", "second", "third"]

    def test_fragment_not_found_goes_last(self) -> None:
        found = _make("found", 4.0, context_fragment="found here")
        missing = _make("missing", 4.0, context_fragment="not in text")
        text = "found here is the content"
        result = sort_chronologically([missing, found], source_text=text)
        assert result[0].lemma == "found"

    def test_tiebreaker_by_id(self) -> None:
        c1 = _make("a", 4.0, context_fragment="same")
        c1.id = 10
        c2 = _make("b", 4.0, context_fragment="same")
        c2.id = 5
        text = "same text"
        result = sort_chronologically([c1, c2], source_text=text)
        assert [c.lemma for c in result] == ["b", "a"]

    def test_empty_list(self) -> None:
        assert sort_chronologically([], source_text="anything") == []

    def test_empty_source_text(self) -> None:
        """All fragments not found in empty text, sort by id."""
        c1 = _make("alpha", 4.0, context_fragment="alpha ctx")
        c1.id = 20
        c2 = _make("beta", 4.0, context_fragment="beta ctx")
        c2.id = 10
        result = sort_chronologically([c1, c2], source_text="")
        assert [c.lemma for c in result] == ["beta", "alpha"]


@pytest.mark.unit
class TestSortByRelevanceWithUsage:
    ORDER = ["neutral", "informal", "formal", "specialized"]

    def test_usage_rank_within_same_band_and_phrasal(self) -> None:
        formal = _make("formal_w", 4.0,
                        usage_distribution=UsageDistribution({"formal": 1.0}))
        informal = _make("informal_w", 4.0,
                          usage_distribution=UsageDistribution({"informal": 1.0}))
        result = sort_by_relevance([formal, informal], usage_order=self.ORDER)
        assert [c.lemma for c in result] == ["informal_w", "formal_w"]

    def test_band_still_beats_usage(self) -> None:
        common_formal = _make("common", 5.0,
                               usage_distribution=UsageDistribution({"formal": 1.0}))
        mid_neutral = _make("mid", 4.0,
                             usage_distribution=UsageDistribution({"neutral": 1.0}))
        result = sort_by_relevance([mid_neutral, common_formal], usage_order=self.ORDER)
        assert [c.lemma for c in result] == ["common", "mid"]

    def test_phrasal_verb_still_beats_usage(self) -> None:
        regular_neutral = _make("walk", 4.0,
                                 usage_distribution=UsageDistribution({"neutral": 1.0}))
        phrasal_formal = _make("give up", 4.0, is_phrasal_verb=True,
                                usage_distribution=UsageDistribution({"formal": 1.0}))
        result = sort_by_relevance([regular_neutral, phrasal_formal], usage_order=self.ORDER)
        assert [c.lemma for c in result] == ["give up", "walk"]

    def test_none_distribution_treated_as_neutral(self) -> None:
        no_usage = _make("unknown", 4.0, usage_distribution=None)
        formal = _make("formal_w", 4.0,
                        usage_distribution=UsageDistribution({"formal": 1.0}))
        result = sort_by_relevance([formal, no_usage], usage_order=self.ORDER)
        assert [c.lemma for c in result] == ["unknown", "formal_w"]

    def test_mixed_distribution_uses_primary_group(self) -> None:
        mixed = _make("cool", 4.0,
                       usage_distribution=UsageDistribution({"informal": 0.4, "neutral": 0.6}))
        pure_informal = _make("gonna", 4.0,
                               usage_distribution=UsageDistribution({"informal": 1.0}))
        result = sort_by_relevance([pure_informal, mixed], usage_order=self.ORDER)
        assert [c.lemma for c in result] == ["cool", "gonna"]

    def test_no_usage_order_backward_compatible(self) -> None:
        formal = _make("formal_w", 4.0,
                        usage_distribution=UsageDistribution({"formal": 1.0}))
        informal = _make("informal_w", 4.0,
                          usage_distribution=UsageDistribution({"informal": 1.0}))
        result = sort_by_relevance([formal, informal])
        assert [c.lemma for c in result] == ["formal_w", "informal_w"]

    def test_custom_user_order(self) -> None:
        custom_order = ["formal", "informal", "neutral"]
        formal = _make("formal_w", 4.0,
                        usage_distribution=UsageDistribution({"formal": 1.0}))
        informal = _make("informal_w", 4.0,
                          usage_distribution=UsageDistribution({"informal": 1.0}))
        result = sort_by_relevance([informal, formal], usage_order=custom_order)
        assert [c.lemma for c in result] == ["formal_w", "informal_w"]

    def test_full_priority_with_usage(self) -> None:
        candidates = [
            _make("rare", 2.0, usage_distribution=UsageDistribution({"neutral": 1.0})),
            _make("mid_formal_b1", 4.0, cefr="B1",
                  usage_distribution=UsageDistribution({"formal": 1.0})),
            _make("mid_neutral_b2", 4.0, cefr="B2",
                  usage_distribution=UsageDistribution({"neutral": 1.0})),
            _make("mid_neutral_b1", 4.0, cefr="B1",
                  usage_distribution=UsageDistribution({"neutral": 1.0})),
            _make("common", 5.0, usage_distribution=UsageDistribution({"informal": 1.0})),
        ]
        result = sort_by_relevance(candidates, usage_order=self.ORDER)
        assert [c.lemma for c in result] == [
            "common",
            "mid_neutral_b1",
            "mid_neutral_b2",
            "mid_formal_b1",
            "rare",
        ]
