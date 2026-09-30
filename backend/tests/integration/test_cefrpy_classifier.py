"""Integration test: VotingCEFRClassifier with all real sources."""
from __future__ import annotations

import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel

from tests.integration.dict_cache_support import make_voting_classifier


@pytest.mark.integration
class TestVotingCEFRClassifierIntegration:
    def setup_method(self) -> None:
        self.classifier = make_voting_classifier()

    def test_common_word_reasonable_level(self) -> None:
        level = self.classifier.classify("happy", "JJ")
        assert level in (CEFRLevel.A1, CEFRLevel.A2)

    def test_advanced_word_high_level(self) -> None:
        level = self.classifier.classify("ubiquitous", "JJ")
        assert level.value >= CEFRLevel.B2.value or level == CEFRLevel.UNKNOWN

    def test_unknown_gibberish(self) -> None:
        level = self.classifier.classify("asdfghjkl", "NN")
        assert level == CEFRLevel.UNKNOWN

    def test_informal_word_not_c2(self) -> None:
        """The whole point: informal words should NOT be classified as C2."""
        level = self.classifier.classify("wow", "UH")
        assert level != CEFRLevel.C2

    def test_nope_takes_level_of_the_only_source_that_knows_it(self) -> None:
        """Sources that don't know a word abstain, so CEFRpy alone decides."""
        level = self.classifier.classify("nope", "NN")
        assert level == CEFRLevel.C2


@pytest.mark.integration
class TestVotingCEFRClassifierWithPriorityIntegration:
    """Full integration: priority sources + fallback sources from dict.db."""

    def setup_method(self) -> None:
        self.classifier = make_voting_classifier()

    def test_common_word_has_level(self) -> None:
        """'happy' should return a reasonable level."""
        level = self.classifier.classify("happy", "JJ")
        assert level in (CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1)

    def test_gibberish_falls_back_to_voting(self) -> None:
        level = self.classifier.classify("asdfghjkl", "NN")
        assert level == CEFRLevel.UNKNOWN

    def test_informal_word_not_c2(self) -> None:
        """Same invariant as before: informal words should not be C2."""
        level = self.classifier.classify("wow", "UH")
        assert level != CEFRLevel.C2

    def test_and_is_basic(self) -> None:
        """'and' is a basic word — sanity check."""
        level = self.classifier.classify("and", "CC")
        assert level in (CEFRLevel.A1, CEFRLevel.A2)
