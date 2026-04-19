from __future__ import annotations

import pytest

from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.candidate_sorting import (
    sort_by_relevance,
    sort_chronologically,
)
from backend.domain.value_objects.candidate_status import CandidateStatus


def _make(
    lemma: str,
    zipf: float,
    *,
    cefr: str | None = "B1",
    occurrences: int = 1,
    is_phrasal_verb: bool = False,
    context_fragment: str = "",
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
