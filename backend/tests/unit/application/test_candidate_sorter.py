from unittest.mock import MagicMock

import pytest
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus

from tests.candidate_sorter_support import candidate_sorter

SOURCE_TEXT = "The scythe was sharp. The feast was long. A scythe again."


def _source() -> Source:
    return Source(
        id=1, raw_text=SOURCE_TEXT, status=SourceStatus.DONE,
        input_method=InputMethod.TEXT_PASTED, content_type=ContentType.TEXT,
    )


def _make(lemma: str, zipf: float, occurrences: int, fragment: str) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma=lemma,
        pos="NOUN",
        cefr_level="B2",
        zipf_frequency=zipf,
        context_fragment=fragment,
        fragment_purity="clean",
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
        self.feast = _make("feast", 3.95, occurrences=1, fragment="The feast was long.")
        self.scythe = _make("scythe", 2.6, occurrences=2, fragment="A scythe again.")

    def _lemmas(self, order: CandidateSortOrder) -> list[str]:
        result = self.sorter.sort([self.scythe, self.feast], _source(), order)
        return [c.lemma for c in result]

    def test_relevance_puts_more_common_word_first(self) -> None:
        assert self._lemmas(CandidateSortOrder.RELEVANCE) == ["feast", "scythe"]

    def test_key_words_puts_repeated_word_first(self) -> None:
        assert self._lemmas(CandidateSortOrder.KEY_WORDS) == ["scythe", "feast"]

    def test_chronological_follows_source_text(self) -> None:
        assert self._lemmas(CandidateSortOrder.CHRONOLOGICAL) == ["feast", "scythe"]
