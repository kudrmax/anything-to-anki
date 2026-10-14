from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.utils.user_vocabulary import UserVocabulary


@pytest.mark.unit
class TestUserVocabulary:
    def setup_method(self) -> None:
        self.known = MagicMock()
        self.known.get_all_pairs.return_value = {("lurk", "VERB"), ("feast", None)}
        self.unknown = MagicMock()
        self.unknown.lemmas.return_value = {"lurk"}
        self.learning = MagicMock()
        self.learning.learning_lemmas.return_value = frozenset({"gull", "feast"})
        self.removals = MagicMock()
        self.removals.contains.return_value = False
        self.vocabulary = UserVocabulary(self.known, self.unknown, self.learning, self.removals)

    def test_word_in_both_lists_is_unknown(self) -> None:
        snapshot = self.vocabulary.snapshot()
        assert snapshot.is_known("feast") is True
        assert snapshot.is_known("lurk") is False
        assert snapshot.is_unknown("lurk") is True

    def test_marking_known_takes_the_word_out_of_unknown(self) -> None:
        self.vocabulary.mark_known("lurk", "VERB")
        self.unknown.remove_by_lemma.assert_called_once_with("lurk")
        self.known.add.assert_called_once_with("lurk", "VERB")

    def test_marking_unknown_takes_every_part_of_speech_out_of_known(self) -> None:
        self.vocabulary.mark_unknown("feast")
        self.known.remove_every_pos.assert_called_once_with("feast")
        self.unknown.add.assert_called_once_with("feast")

    def test_the_snapshot_has_the_learning_words_below_known(self) -> None:
        snapshot = self.vocabulary.snapshot()
        assert snapshot.is_learning("gull") is True
        assert snapshot.is_learning("feast") is False

    def test_marking_known_lifts_an_earlier_removal(self) -> None:
        self.vocabulary.mark_known("gull", None)
        self.removals.discard.assert_called_once_with("gull")

    def test_forgetting_a_known_a_card_added_is_no_removal(self) -> None:
        self.vocabulary.forget_known("feast", None)
        self.known.remove_by_lemma.assert_called_once_with("feast", None)
        self.removals.add.assert_not_called()

    def test_a_new_learn_intent_lifts_an_earlier_removal(self) -> None:
        self.vocabulary.start_learning("gull")
        self.removals.discard.assert_called_once_with("gull")

    def test_maturity_does_not_count_a_word_already_known(self) -> None:
        assert self.vocabulary.mark_mature("feast", "NOUN") is False
        self.known.add.assert_not_called()

    def test_a_mature_word_becomes_known(self) -> None:
        assert self.vocabulary.mark_mature("gull", "NOUN") is True
        self.known.add.assert_called_once_with("gull", "NOUN", from_anki=True)
        self.removals.discard.assert_not_called()

    def test_maturity_leaves_an_unknown_word_alone(self) -> None:
        assert self.vocabulary.mark_mature("lurk", "VERB") is False
        self.known.add.assert_not_called()

    def test_maturity_does_not_put_back_a_word_removed_from_known(self) -> None:
        self.removals.contains.return_value = True
        assert self.vocabulary.mark_mature("gull", "NOUN") is False
        self.known.add.assert_not_called()
