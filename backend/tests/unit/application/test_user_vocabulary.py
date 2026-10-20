from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.utils.knowledge_scope import KnowledgeScope
from backend.application.utils.user_vocabulary import UserVocabulary
from backend.domain.services.decision_rules import UnknownMark

from tests.decision_support import FixedClock


@pytest.mark.unit
class TestUserVocabulary:
    def setup_method(self) -> None:
        self.known = MagicMock()
        self.known.get_all_pairs.return_value = {("lurk", "VERB"), ("feast", None)}
        self.unknown = MagicMock()
        self.unknown.lemmas.return_value = {"lurk"}
        self.learning = MagicMock()
        self.learning.awaiting_export.return_value = frozenset({"gull", "feast"})
        self.learning.active_since.return_value = {}
        self.vocabulary = UserVocabulary(
            self.known, self.unknown,
            KnowledgeScope(FixedClock(), self.known, self.unknown, self.learning),
        )

    def test_word_in_both_lists_is_unknown(self) -> None:
        snapshot = self.vocabulary.snapshot()
        assert snapshot.is_known("feast") is True
        assert snapshot.is_known("lurk") is False
        assert snapshot.is_unknown("lurk") is True

    def test_marking_known_takes_the_word_out_of_unknown(self) -> None:
        self.vocabulary.mark_known("lurk", "VERB")
        self.unknown.remove_by_lemma.assert_called_once_with("lurk")
        self.known.add.assert_called_once_with("lurk", "VERB")

    def test_marking_a_known_word_unknown_waits_for_its_known_removal(self) -> None:
        assert self.vocabulary.mark_unknown("feast") is UnknownMark.REMOVE_KNOWN_FIRST
        self.known.remove_every_pos.assert_not_called()
        self.unknown.add.assert_not_called()

    def test_marking_unknown_takes_every_part_of_speech_out_of_known(self) -> None:
        """A word in both lists stays out of Known: the mark clears the stale entry."""
        self.unknown.lemmas.return_value = {"feast"}
        self.learning.awaiting_export.return_value = frozenset()
        assert self.vocabulary.mark_unknown("feast") is UnknownMark.MARK
        self.known.remove_every_pos.assert_called_once_with("feast")
        self.unknown.add.assert_called_once_with("feast")

    def test_marking_a_new_word_unknown_adds_it(self) -> None:
        assert self.vocabulary.mark_unknown("tern") is UnknownMark.MARK
        self.unknown.add.assert_called_once_with("tern")

    def test_marking_a_word_being_learned_unknown_changes_nothing(self) -> None:
        assert self.vocabulary.mark_unknown("gull") is UnknownMark.IGNORE
        self.known.remove_every_pos.assert_not_called()
        self.unknown.add.assert_not_called()

    def test_forgetting_unknown_takes_the_word_out_of_unknown(self) -> None:
        self.vocabulary.forget_unknown("lurk")
        self.unknown.remove_by_lemma.assert_called_once_with("lurk")

    def test_the_snapshot_has_the_learning_words_below_known(self) -> None:
        snapshot = self.vocabulary.snapshot()
        assert snapshot.is_learning("gull") is True
        assert snapshot.is_learning("feast") is False

    def test_forgetting_known_takes_every_part_of_speech_out_of_known(self) -> None:
        self.vocabulary.forget_every_pos("feast")
        self.known.remove_every_pos.assert_called_once_with("feast")
