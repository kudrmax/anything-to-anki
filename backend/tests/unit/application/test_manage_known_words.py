from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.domain.entities.known_word import KnownWord


@pytest.mark.unit
class TestManageKnownWordsUseCase:
    def setup_method(self) -> None:
        self.known_word_repo = MagicMock()
        self.use_case = ManageKnownWordsUseCase(known_word_repo=self.known_word_repo)

    def test_list_all(self) -> None:
        self.known_word_repo.list_all.return_value = [
            KnownWord(id=1, lemma="run", pos="VERB"),
        ]
        result = self.use_case.list_all()
        assert len(result) == 1
        assert result[0].lemma == "run"

    def test_delete(self) -> None:
        self.use_case.delete(1)
        self.known_word_repo.remove.assert_called_once_with(1)

    def test_add_bulk(self) -> None:
        self.known_word_repo.add.return_value = KnownWord(id=1, lemma="test", pos=None)
        self.use_case.add_bulk(["elaborate", "nuance", "ubiquitous"])
        assert self.known_word_repo.add.call_count == 3
        self.known_word_repo.add.assert_any_call("elaborate", None)
        self.known_word_repo.add.assert_any_call("nuance", None)
        self.known_word_repo.add.assert_any_call("ubiquitous", None)

    def test_add_bulk_empty(self) -> None:
        self.use_case.add_bulk([])
        self.known_word_repo.add.assert_not_called()
