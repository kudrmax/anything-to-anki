from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.manage_known_words import ManageKnownWordsUseCase
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.entities.known_word import KnownWord
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER

from tests.decision_support import NOW
from tests.vocabulary_support import user_vocabulary

DUE = NOW - LEARNING_KNOWN_AFTER - timedelta(days=2)
FRESH = NOW - timedelta(days=1)


@pytest.mark.unit
class TestManageKnownWordsUseCase:
    def setup_method(self) -> None:
        self.known_word_repo = MagicMock()
        self.known_word_repo.get_all_pairs.return_value = {("run", "VERB")}
        self.effects = MagicMock()
        self.use_case = self._use_case()

    def _use_case(self, **vocabulary: object) -> ManageKnownWordsUseCase:
        self.vocabulary = user_vocabulary(self.known_word_repo, **vocabulary)  # type: ignore[arg-type]
        return ManageKnownWordsUseCase(
            vocabulary=self.vocabulary, effects=self.effects,
        )

    def test_list_all(self) -> None:
        self.known_word_repo.list_all.return_value = [
            KnownWord(id=1, lemma="run", pos="VERB"),
        ]
        result = self.use_case.list_all()
        assert len(result) == 1
        assert result[0].lemma == "run"
        assert not result[0].by_timer

    def test_a_word_known_by_its_timer_is_listed_marked_without_an_id(self) -> None:
        self.known_word_repo.list_all.return_value = [KnownWord(id=1, lemma="run", pos="VERB")]
        use_case = self._use_case(active_since={
            "glare": (DUE, FRESH), "drift": (FRESH,), "run": (DUE,), "spark": (DUE,),
        }, unknown_lemmas={"spark"})

        result = use_case.list_all()

        assert [(w.id, w.lemma, w.by_timer) for w in result] == [
            (1, "run", False), (None, "glare", True),
        ]
        assert result[1].created_at == DUE + LEARNING_KNOWN_AFTER

    def test_deleting_a_word_known_by_its_timer_removes_it_from_known_everywhere(
        self,
    ) -> None:
        use_case = self._use_case(active_since={"glare": (DUE,)})
        before = self.vocabulary.of("glare")

        use_case.delete_timer_known("glare")

        self.effects.known_removed.assert_called_once_with("glare", before)

    @pytest.mark.parametrize("lemma", ["run", "fresh", "absent"])
    def test_deleting_by_lemma_a_word_not_known_by_its_timer_does_nothing(
        self, lemma: str,
    ) -> None:
        use_case = self._use_case(active_since={"fresh": (FRESH,)})

        use_case.delete_timer_known(lemma)

        self.effects.known_removed.assert_not_called()
        self.known_word_repo.remove_every_pos.assert_not_called()

    def test_deleting_the_last_entry_of_a_lemma_removes_the_word_from_known(self) -> None:
        self.known_word_repo.list_all.return_value = [KnownWord(id=1, lemma="run", pos="VERB")]
        before = self.vocabulary.of("run")

        self.use_case.delete(1)

        self.effects.known_removed.assert_called_once_with("run", before)

    def test_deleting_one_of_two_entries_of_a_lemma_is_only_an_entry_edit(self) -> None:
        self.known_word_repo.list_all.return_value = [
            KnownWord(id=1, lemma="run", pos="VERB"), KnownWord(id=2, lemma="run", pos="NOUN"),
        ]

        self.use_case.delete(1)

        self.known_word_repo.remove.assert_called_once_with(1)
        self.effects.known_removed.assert_not_called()

    def test_deleting_an_entry_already_gone_changes_nothing_else(self) -> None:
        self.known_word_repo.list_all.return_value = []

        self.use_case.delete(7)

        self.known_word_repo.remove.assert_called_once_with(7)
        self.effects.known_removed.assert_not_called()

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
        unknown_word_repo = MagicMock()
        use_case = ManageKnownWordsUseCase(
            vocabulary=UserVocabulary(self.known_word_repo, unknown_word_repo, MagicMock()),
            effects=self.effects,
        )
        use_case.add_bulk(["nuance"])
        unknown_word_repo.remove_by_lemma.assert_called_once_with("nuance")
