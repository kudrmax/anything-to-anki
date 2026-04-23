"""Integration test: VotingCEFRClassifier with all real sources."""
from __future__ import annotations

from pathlib import Path

import pytest
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.dict_cache.cefr_source import DictCacheCEFRSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader

from backend.domain.ports.cefr_source import CEFRSource

DICT_CACHE_PATH = Path(__file__).resolve().parents[3] / "dictionaries" / ".cache" / "dict.db"

_SKIP_NO_DICT_CACHE = pytest.mark.skipif(
    not DICT_CACHE_PATH.exists(),
    reason=f"dict.db not found at {DICT_CACHE_PATH}",
)


def _make_classifier() -> VotingCEFRClassifier:
    reader = DictCacheReader(DICT_CACHE_PATH)

    cefr_sources: list[CEFRSource] = []
    priority_sources: list[CEFRSource] = []
    for meta in reader.get_cefr_sources():
        src = DictCacheCEFRSource(reader, meta["name"])
        if meta["priority"] == "high":
            priority_sources.append(src)
        else:
            cefr_sources.append(src)
    cefr_sources.append(CefrpyCEFRSource())

    return VotingCEFRClassifier(cefr_sources, priority_sources=priority_sources)


@pytest.mark.integration
@_SKIP_NO_DICT_CACHE
class TestVotingCEFRClassifierIntegration:
    def setup_method(self) -> None:
        self.classifier = _make_classifier()

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

    def test_nope_not_c2(self) -> None:
        """nope should be UNKNOWN (most sources don't know it), not C2."""
        level = self.classifier.classify("nope", "NN")
        assert level != CEFRLevel.C2


@pytest.mark.integration
@_SKIP_NO_DICT_CACHE
class TestVotingCEFRClassifierWithPriorityIntegration:
    """Full integration: priority sources + fallback sources from dict.db."""

    def setup_method(self) -> None:
        self.classifier = _make_classifier()

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
