from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.entities.known_word import KnownWord


@pytest.mark.unit
class TestManageKnownWordsUseCase:
    def setup_method(self) -> None:
        self.known_word_repo = MagicMock()
        self.unknown_word_repo = MagicMock()
        self.review_status = MagicMock()
        self.removals = MagicMock()
        self.use_case = ManageKnownWordsUseCase(
            vocabulary=UserVocabulary(
                self.known_word_repo, self.unknown_word_repo, MagicMock(), self.removals,
            ),
            review_status=self.review_status,
        )

    def test_list_all(self) -> None:
        self.known_word_repo.list_all.return_value = [
            KnownWord(id=1, lemma="run", pos="VERB"),
        ]
        result = self.use_case.list_all()
        assert len(result) == 1
        assert result[0].lemma == "run"

    def test_delete(self) -> None:
        self.known_word_repo.get_by_id.return_value = KnownWord(id=1, lemma="run", pos="VERB")
        self.use_case.delete(1)
        self.known_word_repo.remove.assert_called_once_with(1)
        self.removals.add.assert_called_once_with("run")

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

    def test_known_word_leaves_the_unknown_words(self) -> None:
        self.use_case.add_bulk(["nuance"])
        self.unknown_word_repo.remove_by_lemma.assert_called_once_with("nuance")

    def test_changes_refresh_review_statuses(self) -> None:
        self.use_case.delete(1)
        self.use_case.add_bulk(["nuance"])
        assert self.review_status.refresh_all.call_count == 2
