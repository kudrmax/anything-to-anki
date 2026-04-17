from __future__ import annotations

from pathlib import Path

import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.oxford_cefr_source import OxfordCEFRSource

DATA_PATH = (
    Path(__file__).resolve().parents[3] / "dictionaries" / "cefr" / "oxford5000.csv"
)


@pytest.mark.integration
class TestOxfordCEFRSource:
    def setup_method(self) -> None:
        self.source = OxfordCEFRSource(DATA_PATH)

    def test_known_word_returns_level(self) -> None:
        dist = self.source.get_distribution("happy", "JJ")
        assert dist == {CEFRLevel.A1: 1.0}

    def test_verb_pos_mapping(self) -> None:
        dist = self.source.get_distribution("cool", "VB")
        assert dist == {CEFRLevel.B1: 1.0}

    def test_adjective_pos_mapping(self) -> None:
        dist = self.source.get_distribution("cool", "JJ")
        assert dist == {CEFRLevel.A1: 1.0}

    def test_unknown_word(self) -> None:
        dist = self.source.get_distribution("asdfghjkl", "NN")
        assert dist == {CEFRLevel.UNKNOWN: 1.0}

    def test_wow_exclamation(self) -> None:
        dist = self.source.get_distribution("wow", "UH")
        assert dist == {CEFRLevel.A2: 1.0}

    def test_fallback_to_any_pos(self) -> None:
        # 'happy' is only adjective in Oxford; asking for NN should still find it
        dist = self.source.get_distribution("happy", "NN")
        assert CEFRLevel.UNKNOWN not in dist
