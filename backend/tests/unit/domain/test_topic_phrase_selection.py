from __future__ import annotations

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.topic_phrase_selection import (
    find_shortest_sentence,
    parse_marked_phrase,
    pick_best_candidate_phrase,
)
from backend.domain.value_objects.candidate_status import CandidateStatus

pytestmark = pytest.mark.unit


def _candidate(fragment: str, purity: str = "clean") -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma="negotiate",
        pos="VERB",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment=fragment,
        fragment_purity=purity,
        occurrences=1,
        status=CandidateStatus.PENDING,
    )


class TestParseMarkedPhrase:
    def test_splits_sentence_and_target(self) -> None:
        phrase = parse_marked_phrase("We agreed to **meet halfway** on the price.")
        assert phrase is not None
        assert phrase.text == "We agreed to meet halfway on the price."
        assert phrase.target == "meet halfway"

    def test_returns_none_without_marked_target(self) -> None:
        assert parse_marked_phrase("We agreed to meet halfway.") is None

    def test_returns_none_for_empty_target(self) -> None:
        assert parse_marked_phrase("We agreed **  ** to it.") is None


class TestPickBestCandidatePhrase:
    def test_prefers_clean_phrase_over_shorter_dirty_one(self) -> None:
        dirty = _candidate("They negotiate.", purity="dirty")
        clean = _candidate("We will negotiate the price tomorrow.")
        assert pick_best_candidate_phrase([dirty, clean]) is clean

    def test_prefers_shorter_phrase_among_clean_ones(self) -> None:
        long = _candidate("We will negotiate the price with them tomorrow morning.")
        short = _candidate("We will negotiate the price.")
        assert pick_best_candidate_phrase([long, short]) is short

    def test_returns_none_for_no_candidates(self) -> None:
        assert pick_best_candidate_phrase([]) is None


class TestFindShortestSentence:
    TEXT = (
        "It was a long day. In the end we agreed to meet halfway on almost everything "
        "they asked for that week. They Met Halfway on the price.\n"
        "Nobody wanted to meet."
    )

    def test_finds_shortest_sentence_with_any_variant(self) -> None:
        found = find_shortest_sentence(self.TEXT, {"meet halfway", "met halfway"})
        assert found is not None
        assert found.text == "They Met Halfway on the price."
        assert found.target == "Met Halfway"

    def test_matches_whole_words_only(self) -> None:
        assert find_shortest_sentence("A meeting was planned for the team.", {"meet"}) is None

    def test_matches_across_extra_whitespace(self) -> None:
        found = find_shortest_sentence("They will meet\thalfway on it soon.", {"meet halfway"})
        assert found is not None
        assert found.text == "They will meet halfway on it soon."

    def test_skips_sentences_that_are_too_short(self) -> None:
        assert find_shortest_sentence("Meet halfway.", {"meet halfway"}) is None

    def test_returns_none_without_variants(self) -> None:
        assert find_shortest_sentence(self.TEXT, {" "}) is None
