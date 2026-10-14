from __future__ import annotations

import itertools
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.candidate_sections import new_words, section_of
from backend.domain.services.candidate_sorting import (
    sort_by_key_words,
    sort_by_relevance,
    sort_chronologically,
)
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.frequent_word_threshold import FrequentWordThreshold
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.review_card import ReviewCard
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import EMPTY_VOCABULARY, Vocabulary
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import phrase

if TYPE_CHECKING:
    from backend.domain.value_objects.phrase import Phrase

FREQUENT_ZIPF = 4.5


def _knowledge(vocabulary: Vocabulary = EMPTY_VOCABULARY) -> UserKnowledge:
    return UserKnowledge(vocabulary, CEFRLevel.B1, FREQUENT_ZIPF)


KNOWLEDGE = _knowledge()


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
    position: DocumentPosition | None = None,
    shown: Phrase | None = None,
) -> ReviewCard:
    """A card of its own word; ids follow the order cards are made."""
    card_id = next(_IDS)
    text = shown or _phrase(lemma, context_fragment, unknowns)
    return ReviewCard(
        word=StoredCandidate(
            id=card_id,
            source_id=1,
            lemma=lemma,
            pos=pos,
            cefr_level=cefr,
            zipf_frequency=zipf,
            source_phrase=text,
            occurrences=occurrences,
            status=CandidateStatus.PENDING,
            is_phrasal_verb=is_phrasal_verb,
            usage_distribution=usage_distribution,
        ),
        occurrence=Occurrence(
            id=card_id, candidate_id=card_id, origin=OccurrenceOrigin.AUTO,
            source_phrase=text, phrase_position=position, key=None, fragment_score=None,
            shown_by=ShownBy.SELECTION,
        ),
        word_status=WordStatus.PENDING,
    )


_IDS = itertools.count(1)


def _with_id(card: ReviewCard, card_id: int) -> ReviewCard:
    return ReviewCard(
        word=replace(card.word, id=card_id),
        occurrence=replace(card.occurrence, id=card_id, candidate_id=card_id),
        word_status=card.word_status,
    )


def _decided(card: ReviewCard, status: WordStatus) -> ReviewCard:
    return replace(card, word_status=status)


def _skipped(card: ReviewCard) -> ReviewCard:
    return replace(card, occurrence=replace(card.occurrence, skipped=True))


def _phrase(lemma: str, context_fragment: str, unknowns: int) -> Phrase:
    strange = [f"strange{i}" for i in range(unknowns)]
    text = " ".join([context_fragment or f"context for {lemma}", *strange])
    return phrase(text, lemma, new=strange)


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

    def test_identical_keys_keep_the_order_words_were_made(self) -> None:
        """Two cards with identical sort keys go by their words' ids, whatever the input."""
        a = _make("alpha", 4.0)
        b = _make("beta", 4.0)
        assert [c.lemma for c in sort_by_relevance([a, b])] == ["alpha", "beta"]
        assert [c.lemma for c in sort_by_relevance([b, a])] == ["alpha", "beta"]

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


def _at(block: int, line: int, char: int) -> DocumentPosition:
    return DocumentPosition(block, line, char, line, char + 1)


@pytest.mark.unit
class TestSortChronologically:
    def test_by_position_in_the_document(self) -> None:
        c1 = _make("first", 4.0, position=_at(0, 3, 0))
        c2 = _make("second", 4.0, position=_at(1, 0, 5))
        c3 = _make("third", 4.0, position=_at(1, 0, 9))
        result = sort_chronologically([c3, c1, c2])
        assert [c.lemma for c in result] == ["first", "second", "third"]

    def test_phrase_without_a_place_goes_last(self) -> None:
        placed = _make("placed", 4.0, position=_at(5, 0, 0))
        example = _make("example", 4.0)
        result = sort_chronologically([example, placed])
        assert [c.lemma for c in result] == ["placed", "example"]

    def test_tiebreaker_by_id(self) -> None:
        c1 = _with_id(_make("a", 4.0, position=_at(0, 0, 0)), 10)
        c2 = _with_id(_make("b", 4.0, position=_at(0, 0, 0)), 5)
        result = sort_chronologically([c1, c2])
        assert [c.lemma for c in result] == ["b", "a"]

    def test_empty_list(self) -> None:
        assert sort_chronologically([]) == []

    def test_phrases_without_places_keep_the_order_they_were_added(self) -> None:
        """A topic's phrases have no document: they stay as collected."""
        c1 = _with_id(_make("alpha", 4.0), 20)
        c2 = _with_id(_make("beta", 4.0), 10)
        result = sort_chronologically([c1, c2])
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
        result = sort_by_relevance(
            candidates, frequent_threshold=self.THRESHOLD, knowledge=KNOWLEDGE,
        )
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


@pytest.mark.unit
class TestSortByKeyWords:
    """Words the text leans on most come first; useless ones still go down."""

    THRESHOLD = FrequentWordThreshold.from_key("4.5")

    def _lemmas(self, candidates: list[StoredCandidate]) -> list[str]:
        result = sort_by_key_words(
            candidates, frequent_threshold=self.THRESHOLD, knowledge=KNOWLEDGE,
        )
        return [c.lemma for c in result]

    def test_more_occurrences_go_first(self) -> None:
        once = _make("feast", 3.95, occurrences=1)
        often = _make("scythe", 2.6, occurrences=7)
        assert self._lemmas([once, often]) == ["scythe", "feast"]

    def test_occurrences_beat_frequency_in_language(self) -> None:
        common_once = _make("dare", 4.3, occurrences=1)
        rare_twice = _make("gallows", 2.4, occurrences=2)
        assert self._lemmas([common_once, rare_twice]) == ["gallows", "dare"]

    def test_rarer_word_goes_first_on_equal_occurrences(self) -> None:
        common = _make("dare", 4.3, occurrences=3)
        rare = _make("gallows", 2.4, occurrences=3)
        assert self._lemmas([common, rare]) == ["gallows", "dare"]

    def test_phrase_with_other_new_words_goes_below_ready_ones(self) -> None:
        clean = _make("feast", 3.95, occurrences=1)
        dirty = _make("scythe", 2.6, occurrences=5, unknowns=2)
        assert self._lemmas([clean, dirty]) == ["feast", "scythe"]

    def test_cleaner_phrase_goes_first_on_equal_word(self) -> None:
        dirty = _make("scythe", 2.6, occurrences=5, unknowns=1)
        clean = _make("scythe", 2.6, occurrences=5)
        result = sort_by_key_words(
            [dirty, clean], frequent_threshold=self.THRESHOLD, knowledge=KNOWLEDGE,
        )
        assert [len(new_words(c.phrase, KNOWLEDGE)) for c in result] == [0, 1]

    def test_too_frequent_word_goes_below_even_if_repeated(self) -> None:
        frequent = _make("concept", 4.77, occurrences=9)
        rare = _make("feast", 3.95, occurrences=1)
        assert self._lemmas([frequent, rare]) == ["feast", "concept"]

    def test_junk_goes_to_the_very_bottom(self) -> None:
        junk = _make("turking", 0.0, occurrences=12)
        interjection = _make("heh", 3.67, pos="INTJ", occurrences=12)
        frequent = _make("concept", 4.77)
        assert self._lemmas([junk, interjection, frequent]) == ["concept", "turking", "heh"]

    def test_empty_list(self) -> None:
        assert sort_by_key_words([]) == []


@pytest.mark.unit
class TestDoneLastInTextOrder:
    def test_done_cards_go_below_open_ones_keeping_order(self) -> None:
        a, b, c, d, e = (_make(name, 4.0) for name in ("a", "b", "c", "d", "e"))
        cards = [_skipped(a), b, _decided(c, WordStatus.LEARN), _decided(d, WordStatus.KNOWN), e]
        result = sort_chronologically(cards)
        assert [card.lemma for card in result] == ["b", "e", "a", "c", "d"]


@pytest.mark.unit
class TestSections:
    """Ready cards first, then cards with other new words, then probably known; decided sink
    inside their own section."""

    THRESHOLD = FrequentWordThreshold.from_key("4.5")

    def _lemmas(
        self, candidates: list[ReviewCard], vocabulary: Vocabulary = EMPTY_VOCABULARY,
    ) -> list[str]:
        result = sort_by_relevance(
            candidates, frequent_threshold=self.THRESHOLD, knowledge=_knowledge(vocabulary),
        )
        return [c.lemma for c in result]

    def test_decided_ready_card_stays_above_pending_extra_one(self) -> None:
        decided = _decided(_make("feast", 3.95), WordStatus.LEARN)
        extra = _make("scythe", 2.6, unknowns=1)
        assert self._lemmas([extra, decided]) == ["feast", "scythe"]

    def test_decided_card_goes_below_pending_one_of_its_section(self) -> None:
        decided = _skipped(_make("feast", 3.95))
        pending = _make("gallows", 2.4)
        assert self._lemmas([decided, pending]) == ["gallows", "feast"]

    def test_known_word_no_longer_holds_phrase_back(self) -> None:
        extra = _make("feast", 3.95, unknowns=1)
        ready = _make("scythe", 2.6)
        known = Vocabulary.of(known={"strange0"}, unknown=set())
        assert self._lemmas([ready, extra]) == ["scythe", "feast"]
        assert self._lemmas([ready, extra], known) == ["feast", "scythe"]

    def test_unknown_word_holds_phrase_back_even_if_common(self) -> None:
        held = _make("scythe", 2.6)
        ready = _make("feast", 3.95)
        unknown = Vocabulary.of(known=set(), unknown={"context"})
        assert self._lemmas([held, ready], unknown) == ["feast", "scythe"]

    def test_section_of_each_kind(self) -> None:
        threshold = self.THRESHOLD
        assert section_of(_make("feast", 3.95), KNOWLEDGE, threshold) is (
            CandidateSection.READY
        )
        assert section_of(_make("scythe", 2.6, unknowns=1), KNOWLEDGE, threshold) is (
            CandidateSection.EXTRA
        )
        assert section_of(_make("concept", 4.77, unknowns=1), KNOWLEDGE, threshold) is (
            CandidateSection.PROBABLY_KNOWN
        )

    def test_new_words_are_listed_once(self) -> None:
        candidate = _make(
            "scythe", 2.6, shown=phrase("grim grim the scythe", "scythe", new=["grim"]),
        )
        assert new_words(candidate.phrase, KNOWLEDGE) == ["grim"]

    def test_new_target_is_not_an_extra_word(self) -> None:
        candidate = _make("scythe", 2.6, shown=phrase("the scythe", "scythe", new=["scythe"]))
        assert new_words(candidate.phrase, KNOWLEDGE) == []
