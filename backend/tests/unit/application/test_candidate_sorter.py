from unittest.mock import MagicMock

import pytest
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.document_position import DocumentPosition
from backend.domain.value_objects.review_card import ReviewCard
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

    def test_every_card_gets_its_section_and_progress_counts_ready_ones(self) -> None:
        learned = card(
            word(3, "gallows", status=WordStatus.LEARN),
            occurrence(3, 3, phrase("the gallows stood", "gallows")),
        )
        dirty = card(word(4, "ember"), occurrence(4, 4, phrase("an ember zephyr", "ember",
                                                               new=("zephyr",))))
        arranged = self.sorter.arrange([learned, dirty])
        assert arranged.section(learned) is CandidateSection.READY
        assert arranged.section(dirty) is CandidateSection.EXTRA
        assert (arranged.progress().decided, arranged.progress().total) == (1, 1)
