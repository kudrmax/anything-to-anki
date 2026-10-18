"""Cards of the review list: sections, progress and order by shown phrase."""
from __future__ import annotations

from dataclasses import replace

import pytest
from backend.domain.entities.occurrence import Occurrence
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.services.candidate_sections import ready_progress, section_of
from backend.domain.services.candidate_sorting import (
    sort_by_key_words,
    sort_by_relevance,
    sort_chronologically,
)
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import CardChoice
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.domain.value_objects.review_card import ReviewCard
from backend.domain.value_objects.user_knowledge import UserKnowledge
from backend.domain.value_objects.vocabulary import Vocabulary
from backend.domain.value_objects.word_status import WordStatus

from tests.phrase_support import phrase

pytestmark = pytest.mark.unit

KNOWLEDGE = UserKnowledge(Vocabulary.of(set(), set()), CEFRLevel.B1, 4.5)


def _word(word_id: int, lemma: str, zipf: float = 3.0, occurrences: int = 1) -> StoredCandidate:
    return StoredCandidate(
        source_id=1, lemma=lemma, pos="NOUN", cefr_level="B1", zipf_frequency=zipf,
        occurrences=occurrences, status=WordStatus.NEW,
        id=word_id,
    )


def _card(
    word: StoredCandidate,
    phrase_id: int,
    text: str = "",
    *,
    new: tuple[str, ...] = (),
    status: WordStatus = WordStatus.NEW,
    skipped: bool = False,
    elsewhere: ElsewhereStatus | None = None,
    at: int | None = None,
) -> ReviewCard:
    assert word.id is not None
    return ReviewCard(
        word=replace(word, status=status),
        occurrence=Occurrence(
            id=phrase_id, candidate_id=word.id, origin=OccurrenceOrigin.AUTO,
            source_phrase=phrase(text or f"a {word.lemma} here {' '.join(new)}".strip(),
                                 word.lemma, new=new),
            phrase_position=DocumentPosition(0, 0, at, 0, at + 1) if at is not None else None,
            key=None, fragment_score=None, shown_by=ShownBy.SELECTION,
            choice=CardChoice.SKIP if skipped else CardChoice.NONE,
        ),
        elsewhere=elsewhere,
    )


class TestSections:
    def test_each_card_takes_the_section_of_its_own_phrase(self) -> None:
        word = _word(1, "glare")
        clean = _card(word, 1)
        dirty = _card(word, 2, new=("zephyr",))
        assert section_of(clean, KNOWLEDGE, None) is CandidateSection.READY
        assert section_of(dirty, KNOWLEDGE, None) is CandidateSection.EXTRA

    def test_a_learning_lemma_counts_as_new_in_other_phrases(self) -> None:
        learning = UserKnowledge(
            Vocabulary.of(set(), set(), learning={"spark"}), CEFRLevel.B1, 4.5,
        )
        card = _card(_word(1, "glare"), 1, "a glare and a spark")
        assert section_of(card, learning, None) is CandidateSection.EXTRA


class TestDone:
    @pytest.mark.parametrize(("status", "skipped", "elsewhere", "done"), [
        (WordStatus.NEW, False, None, False),
        (WordStatus.LEARN, False, None, True),
        (WordStatus.KNOWN, False, None, True),
        (WordStatus.NEW, True, None, True),
        (WordStatus.NEW, False, ElsewhereStatus.KNOWN, True),
        (WordStatus.NEW, False, ElsewhereStatus.LEARNING, True),
    ])
    def test_a_card_is_done_when_its_word_is_decided_its_phrase_skipped_or_done_elsewhere(
        self, status: WordStatus, skipped: bool, elsewhere: ElsewhereStatus | None, done: bool,
    ) -> None:
        card = _card(_word(1, "glare"), 1, status=status, skipped=skipped, elsewhere=elsewhere)
        assert card.is_done is done


class TestProgress:
    def test_ready_cards_count_and_cards_done_elsewhere_do_not(self) -> None:
        word = _word(1, "glare")
        cards = [
            (_card(word, 1, status=WordStatus.LEARN), CandidateSection.READY),
            (_card(word, 2, status=WordStatus.LEARN), CandidateSection.READY),
            (_card(_word(2, "spark"), 3), CandidateSection.READY),
            (_card(_word(3, "flame"), 4, elsewhere=ElsewhereStatus.KNOWN), CandidateSection.READY),
            (_card(_word(4, "ember"), 5), CandidateSection.EXTRA),
        ]
        assert ready_progress(cards) == DecisionProgress(decided=2, total=3)


def _words(cards: list[ReviewCard]) -> list[int | None]:
    return [c.word.id for c in cards]


class TestCardsOfAWordStandTogether:
    def test_by_relevance(self) -> None:
        common, middle = _word(1, "common", zipf=4.4), _word(2, "middle", zipf=2.6)
        cards = [_card(common, 1), _card(middle, 2), _card(common, 3)]
        assert _words(sort_by_relevance(cards, knowledge=KNOWLEDGE)) == [1, 1, 2]

    def test_by_key_words(self) -> None:
        often, once = _word(1, "often", occurrences=5), _word(2, "once")
        cards = [_card(often, 1), _card(once, 2), _card(often, 3)]
        assert _words(sort_by_key_words(cards, knowledge=KNOWLEDGE)) == [1, 1, 2]

    def test_in_text_order_a_word_stands_where_its_first_open_card_is(self) -> None:
        glare, spark = _word(1, "glare"), _word(2, "spark")
        cards = [_card(glare, 1, at=10), _card(spark, 2, at=20), _card(glare, 3, at=30)]
        ordered = sort_chronologically(cards)
        assert [c.occurrence.id for c in ordered] == [1, 3, 2]

    def test_a_done_card_goes_down_with_its_word_kept_together(self) -> None:
        glare, spark = _word(1, "glare"), _word(2, "spark")
        cards = [
            _card(glare, 1, at=10, skipped=True),
            _card(spark, 2, at=20),
            _card(glare, 3, at=30),
        ]
        assert [c.occurrence.id for c in sort_chronologically(cards)] == [2, 3, 1]

    def test_cards_of_a_word_in_different_sections_follow_their_sections(self) -> None:
        glare, spark = _word(1, "glare"), _word(2, "spark")
        cards = [_card(glare, 1, new=("zephyr",)), _card(spark, 2), _card(glare, 3)]
        ordered = sort_by_relevance(cards, knowledge=KNOWLEDGE)
        assert [c.occurrence.id for c in ordered] == [3, 2, 1]
