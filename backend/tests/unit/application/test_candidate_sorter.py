from unittest.mock import MagicMock

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.document_position import DocumentPosition

from tests.candidate_sorter_support import candidate_sorter
from tests.phrase_support import phrase

SOURCE_TEXT = "The scythe was sharp. The feast was long. A scythe again."


def _make(
    lemma: str, zipf: float, occurrences: int, fragment: str, block: int,
) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        phrase_position=DocumentPosition(block, 0, 0, 0, len(fragment)),
        lemma=lemma,
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=zipf,
        source_phrase=phrase(fragment, lemma, new=(lemma,)),
        occurrences=occurrences,
        status=CandidateStatus.PENDING,
        is_phrasal_verb=False,
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
        result = self.sorter.sort([self.scythe, self.feast], order)
        return [c.lemma for c in result]

    def test_relevance_puts_more_common_word_first(self) -> None:
        assert self._lemmas(CandidateSortOrder.RELEVANCE) == ["feast", "scythe"]

    def test_key_words_puts_repeated_word_first(self) -> None:
        assert self._lemmas(CandidateSortOrder.KEY_WORDS) == ["scythe", "feast"]

    def test_chronological_follows_the_document(self) -> None:
        assert self._lemmas(CandidateSortOrder.CHRONOLOGICAL) == ["feast", "scythe"]
