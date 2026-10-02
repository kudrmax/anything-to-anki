from __future__ import annotations

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.candidate_sorting import (
    sort_by_relevance,
    sort_chronologically,
)
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
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
    pos: str = "NOUN",
    unknowns: int = 0,
) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma=lemma,
        pos=pos,
        cefr_level=cefr,
        zipf_frequency=zipf,
        context_fragment=context_fragment or f"context for {lemma}",
        fragment_purity="clean" if unknowns == 0 else "dirty",
        fragment_unknown_count=unknowns,
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

    def test_phrasal_verbs_go_after_regular_words(self) -> None:
        regulars = [_make(f"word{i}", 4.0) for i in range(3)]
        phrasals = [_make(f"pv{i}", 4.0, is_phrasal_verb=True) for i in range(2)]
        result = sort_by_relevance(phrasals + regulars)
        assert [c.lemma for c in result] == ["word0", "word1", "word2", "pv0", "pv1"]

    def test_phrasal_verb_goes_after_regular_word_of_any_band(self) -> None:
        phrasal_common = _make("give up", 5.0, is_phrasal_verb=True)
        regular_rare = _make("explain", 2.0)
        result = sort_by_relevance([phrasal_common, regular_rare])
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
        """band DESC > cefr ASC > occurrences DESC, phrasal verbs after regular words."""
        candidates = [
            _make("rare_phrasal", 2.0, is_phrasal_verb=True),    # RARE, phrasal
            _make("common_a2", 5.0, cefr="A2"),                  # COMMON
            _make("mid_b1_many", 4.0, cefr="B1", occurrences=5), # MID
            _make("mid_b1_few", 4.0, cefr="B1", occurrences=1),  # MID
            _make("mid_a1", 4.0, cefr="A1"),                     # MID
        ]
        result = sort_by_relevance(candidates)
        assert [c.lemma for c in result] == [
            "common_a2", "mid_a1", "mid_b1_many", "mid_b1_few", "rare_phrasal",
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

    def test_phrasal_verb_goes_after_regular_words_regardless_of_usage(self) -> None:
        regulars = [
            _make("walk", 4.0, usage_distribution=UsageDistribution({"formal": 1.0})),
        ]
        phrasals = [
            _make("give up", 4.0, is_phrasal_verb=True,
                  usage_distribution=UsageDistribution({"neutral": 1.0})),
        ]
        result = sort_by_relevance(phrasals + regulars, usage_order=self.ORDER)
        assert [c.lemma for c in result] == ["walk", "give up"]

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


@pytest.mark.unit
class TestSortByRelevanceGroups:
    """Probably useless cards go down instead of disappearing."""

    THRESHOLD = FrequentWordThreshold.from_key("4.5")

    def _lemmas(self, candidates: list[StoredCandidate]) -> list[str]:
        result = sort_by_relevance(candidates, frequent_threshold=self.THRESHOLD)
        return [c.lemma for c in result]

    def test_too_frequent_word_goes_below_rarer_one(self) -> None:
        frequent = _make("concept", 4.77)
        rare = _make("feast", 3.95)
        assert self._lemmas([frequent, rare]) == ["feast", "concept"]

    def test_no_threshold_keeps_frequent_word_on_top(self) -> None:
        frequent = _make("concept", 4.77)
        rare = _make("feast", 3.95)
        result = sort_by_relevance([rare, frequent])
        assert [c.lemma for c in result] == ["concept", "feast"]

    def test_dirty_phrase_goes_below_clean_one(self) -> None:
        dirty = _make("paleontology", 2.8, unknowns=1)
        clean = _make("feast", 3.95)
        assert self._lemmas([dirty, clean]) == ["feast", "paleontology"]

    def test_fewer_extra_unknowns_go_higher(self) -> None:
        two = _make("cider", 3.5, unknowns=2)
        one = _make("dare", 4.3, unknowns=1)
        assert self._lemmas([two, one]) == ["dare", "cider"]

    def test_clean_phrasal_verb_goes_above_dirty_regular_word(self) -> None:
        dirty = _make("paleontology", 2.8, unknowns=1)
        phrasal = _make("chip in", 4.3, is_phrasal_verb=True)
        assert self._lemmas([dirty, phrasal]) == ["chip in", "paleontology"]

    def test_dirty_rare_word_goes_above_too_frequent_clean_one(self) -> None:
        frequent = _make("concept", 4.77)
        dirty = _make("paleontology", 2.8, unknowns=1)
        assert self._lemmas([frequent, dirty]) == ["paleontology", "concept"]

    def test_word_missing_from_dictionary_goes_to_the_very_bottom(self) -> None:
        junk = _make("turking", 0.0)
        frequent = _make("concept", 4.77)
        assert self._lemmas([junk, frequent]) == ["concept", "turking"]

    def test_interjection_goes_to_the_very_bottom(self) -> None:
        interjection = _make("heh", 3.67, pos="INTJ")
        frequent = _make("concept", 4.77)
        assert self._lemmas([interjection, frequent]) == ["concept", "heh"]

    def test_collocation_missing_from_dictionary_is_not_junk(self) -> None:
        collocation = _make("starting salary", 0.0)
        frequent = _make("concept", 4.77)
        assert self._lemmas([frequent, collocation]) == ["starting salary", "concept"]
