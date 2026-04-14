from __future__ import annotations

from pathlib import Path

import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.kelly_cefr_source import KellyCEFRSource

DATA_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "backend" / "resources" / "cefr" / "kelly.csv"
)


@pytest.mark.integration
class TestKellyCEFRSource:
    def setup_method(self) -> None:
        self.source = KellyCEFRSource(DATA_PATH)

    def test_known_word_returns_level(self) -> None:
        dist = self.source.get_distribution("happy", "JJ")
        assert dist == {CEFRLevel.A1: 1.0}

    def test_unknown_word(self) -> None:
        dist = self.source.get_distribution("asdfghjkl", "NN")
        assert dist == {CEFRLevel.UNKNOWN: 1.0}

    def test_pos_matching(self) -> None:
        dist_jj = self.source.get_distribution("cool", "JJ")
        dist_vb = self.source.get_distribution("cool", "VB")
        assert dist_jj == {CEFRLevel.B1: 1.0}
        assert dist_vb == {CEFRLevel.B2: 1.0}

    def test_wow_exclamation(self) -> None:
        dist = self.source.get_distribution("wow", "UH")
        assert dist == {CEFRLevel.B1: 1.0}

    def test_fallback_to_any_pos(self) -> None:
        # 'happy' is Adjective; asking with NN should still find via fallback
        dist = self.source.get_distribution("happy", "NN")
        assert CEFRLevel.UNKNOWN not in dist
