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
