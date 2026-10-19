from unittest.mock import MagicMock

import pytest
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.elsewhere import ElsewhereStatus
from backend.domain.value_objects.review_card import CardRow, ReviewCard
from backend.domain.value_objects.word_status import WordStatus

from tests.candidate_sorter_support import candidate_sorter
from tests.card_support import card, occurrence, word
from tests.phrase_support import phrase

SOURCE_TEXT = "The scythe was sharp. The feast was long. A scythe again."


def _make(
    lemma: str, zipf: float, occurrences: int, fragment: str, block: int,
) -> ReviewCard:
    word_id = block + 1
    return card(
        word(word_id, lemma, zipf_frequency=zipf, occurrences=occurrences),
        occurrence(
            word_id, word_id, phrase(fragment, lemma, new=(lemma,)),
            phrase_position=DocumentPosition(block, 0, 0, 0, len(fragment)),
        ),
    )


@pytest.mark.unit
class TestCandidateSorter:
    def setup_method(self) -> None:
        settings_repo = MagicMock()
        settings_repo.get.return_value = None
        self.sorter = candidate_sorter(settings_repo)
        self.feast = _make("feast", 3.95, occurrences=1, fragment="The feast was long.", block=0)
        self.scythe = _make("scythe", 2.6, occurrences=2, fragment="A scythe again.", block=1)

    def _lemmas(self, order: CandidateSortOrder) -> list[str]:
        result = self.sorter.arrange([self.scythe, self.feast], order)
        return [c.lemma for c in result.cards]

    def test_relevance_puts_more_common_word_first(self) -> None:
        assert self._lemmas(CandidateSortOrder.RELEVANCE) == ["feast", "scythe"]

    def test_key_words_puts_repeated_word_first(self) -> None:
        assert self._lemmas(CandidateSortOrder.KEY_WORDS) == ["scythe", "feast"]

    def test_chronological_follows_the_document(self) -> None:
        assert self._lemmas(CandidateSortOrder.CHRONOLOGICAL) == ["feast", "scythe"]

    def test_a_done_card_is_reviewed_and_an_open_card_keeps_its_section(self) -> None:
        learned = card(
            word(3, "gallows", status=WordStatus.LEARN),
            occurrence(3, 3, phrase("the gallows stood", "gallows")),
        )
        dirty = card(word(4, "ember"), occurrence(
            4, 4, phrase("an ember zephyr", "ember", new=("zephyr",)),
            earned_section=CandidateSection.EXTRA,
        ))
        arranged = self.sorter.arrange([learned, dirty, self.feast])
        assert arranged.section(learned) is CandidateSection.REVIEWED
        assert arranged.section(dirty) is CandidateSection.EXTRA
        assert arranged.section(self.feast) is CandidateSection.READY
        assert [c.lemma for c in arranged.cards] == ["feast", "ember", "gallows"]
        assert self.sorter.section(learned) is CandidateSection.REVIEWED
        assert self.sorter.section(dirty) is CandidateSection.EXTRA

    def test_an_open_card_stands_in_its_stored_section_whatever_the_user_knows_now(self) -> None:
        stamped = card(
            word(3, "ember"),
            occurrence(3, 3, phrase("an ember", "ember"), earned_section=CandidateSection.EXTRA),
        )

        arranged = self.sorter.arrange([stamped, self.feast])

        assert arranged.section(stamped) is CandidateSection.EXTRA
        assert self.sorter.section(stamped) is CandidateSection.EXTRA
        assert [c.lemma for c in arranged.cards] == ["feast", "ember"]

    def test_a_done_card_is_reviewed_whatever_its_stored_section(self) -> None:
        learned = card(
            word(3, "ember", status=WordStatus.LEARN),
            occurrence(3, 3, phrase("an ember", "ember"), earned_section=CandidateSection.EXTRA),
        )

        assert self.sorter.arrange([learned]).section(learned) is CandidateSection.REVIEWED

    def test_order_inside_a_section_still_follows_new_words(self) -> None:
        many = card(
            word(3, "ember"),
            occurrence(
                3, 3, phrase("an ember quill zephyr", "ember", new=("quill", "zephyr")),
                earned_section=CandidateSection.EXTRA,
            ),
        )
        few = card(
            word(4, "cinder"),
            occurrence(
                4, 4, phrase("a cinder quill", "cinder", new=("quill",)),
                earned_section=CandidateSection.EXTRA,
            ),
        )

        arranged = self.sorter.arrange([many, few])

        assert [c.lemma for c in arranged.cards] == ["cinder", "ember"]

    def test_progress_is_reviewed_among_reviewed_and_open_ready(self) -> None:
        skipped_extra = card(
            word(3, "ember"),
            occurrence(
                3, 3, phrase("an ember zephyr", "ember", new=("zephyr",)), skipped=True,
                earned_section=CandidateSection.EXTRA,
            ),
        )
        open_extra = card(word(4, "cinder"), occurrence(
            4, 4, phrase("a cinder quill", "cinder", new=("quill",)),
            earned_section=CandidateSection.EXTRA,
        ))
        known_elsewhere = card(
            word(5, "gallows"), occurrence(5, 5, phrase("the gallows stood", "gallows")),
            elsewhere=ElsewhereStatus.KNOWN,
        )
        arranged = self.sorter.arrange(
            [skipped_extra, open_extra, known_elsewhere, self.feast, self.scythe],
        )
        assert arranged.progress() == DecisionProgress(decided=2, total=4)

    def test_progress_of_sources_counts_cards_done_elsewhere(self) -> None:
        rows = [
            _row(1, "gallows", "the gallows stood", elsewhere=ElsewhereStatus.LEARNING),
            _row(2, "ember", "an ember zephyr", CandidateSection.EXTRA, skipped=True),
            _row(3, "cinder", "a cinder quill", CandidateSection.EXTRA),
            _row(4, "concept", "a concept here", CandidateSection.PROBABLY_KNOWN, zipf=4.77),
            _row(5, "feast", "the feast"),
        ]
        assert self.sorter.progress({7: rows}) == {7: DecisionProgress(decided=2, total=3)}


def _row(
    word_id: int, lemma: str, text: str, earned: CandidateSection = CandidateSection.READY,
    *, zipf: float = 3.0, skipped: bool = False, elsewhere: ElsewhereStatus | None = None,
) -> CardRow:
    return CardRow(
        source_id=7, word_id=word_id, phrase_id=word_id, lemma=lemma, pos="NOUN",
        zipf_frequency=zipf, word_status=WordStatus.NEW, skipped=skipped,
        phrase=phrase(text, lemma), earned_section=earned, elsewhere=elsewhere,
    )
