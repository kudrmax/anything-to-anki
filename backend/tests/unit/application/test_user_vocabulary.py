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
        self.marks = MagicMock()
        self.marks.known_lemmas.return_value = {"feast"}
        self.marks.unknown_lemmas.return_value = {"lurk"}
        self.learning = MagicMock()
        self.learning.awaiting_export.return_value = frozenset({"gull", "feast"})
        self.learning.active_since.return_value = {}
        self.vocabulary = UserVocabulary(
            self.marks, KnowledgeScope(FixedClock(), self.marks, self.learning),
        )

    def test_a_word_is_known_or_unknown(self) -> None:
        snapshot = self.vocabulary.snapshot()
        assert snapshot.is_known("feast") is True
        assert snapshot.is_known("lurk") is False
        assert snapshot.is_unknown("lurk") is True

    def test_marking_known_takes_the_word_out_of_unknown(self) -> None:
        self.vocabulary.mark_known("lurk", "VERB")
        self.marks.mark_known.assert_called_once_with("lurk", "VERB")

    def test_marking_a_known_word_unknown_waits_for_its_known_removal(self) -> None:
        assert self.vocabulary.mark_unknown("feast") is UnknownMark.REMOVE_KNOWN_FIRST
        self.marks.remove_known.assert_not_called()
        self.marks.mark_unknown.assert_not_called()

    def test_marking_a_new_word_unknown_adds_it(self) -> None:
        assert self.vocabulary.mark_unknown("tern") is UnknownMark.MARK
        self.marks.mark_unknown.assert_called_once_with("tern")

    def test_marking_a_word_being_learned_unknown_changes_nothing(self) -> None:
        assert self.vocabulary.mark_unknown("gull") is UnknownMark.IGNORE
        self.marks.remove_known.assert_not_called()
        self.marks.mark_unknown.assert_not_called()

    def test_forgetting_unknown_takes_the_word_out_of_unknown(self) -> None:
        self.vocabulary.forget_unknown("lurk")
        self.marks.remove_unknown.assert_called_once_with("lurk")

    def test_the_snapshot_has_the_learning_words_below_known(self) -> None:
        snapshot = self.vocabulary.snapshot()
        assert snapshot.is_learning("gull") is True
        assert snapshot.is_learning("feast") is False

    def test_forgetting_known_takes_every_part_of_speech_out_of_known(self) -> None:
        self.vocabulary.forget_every_pos("feast")
        self.marks.remove_known.assert_called_once_with("feast")
