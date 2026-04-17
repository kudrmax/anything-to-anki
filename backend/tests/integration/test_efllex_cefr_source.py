from __future__ import annotations

from pathlib import Path

import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.efllex_cefr_source import EFLLexCEFRSource

DATA_PATH = (
    Path(__file__).resolve().parents[3] / "dictionaries" / "cefr" / "efllex.tsv"
)


@pytest.mark.integration
class TestEFLLexCEFRSource:
    def setup_method(self) -> None:
        self.source = EFLLexCEFRSource(DATA_PATH)

    def test_known_word_returns_distribution(self) -> None:
        dist = self.source.get_distribution("happy", "JJ")
        assert sum(dist.values()) == pytest.approx(1.0)
        # happy should have most weight in A1-A2
        assert dist.get(CEFRLevel.A1, 0) + dist.get(CEFRLevel.A2, 0) > 0.5

    def test_word_with_spread(self) -> None:
        dist = self.source.get_distribution("cool", "JJ")
        assert sum(dist.values()) == pytest.approx(1.0)
        non_zero = [lvl for lvl, p in dist.items() if p > 0 and lvl != CEFRLevel.UNKNOWN]
        assert len(non_zero) >= 2

    def test_unknown_word_returns_unknown(self) -> None:
        dist = self.source.get_distribution("asdfghjkl", "NN")
        assert dist == {CEFRLevel.UNKNOWN: 1.0}

    def test_pos_tag_matching(self) -> None:
        dist_jj = self.source.get_distribution("cool", "JJ")
        dist_vb = self.source.get_distribution("cool", "VB")
        assert dist_jj != dist_vb

    def test_wow_is_known(self) -> None:
        dist = self.source.get_distribution("wow", "UH")
        assert CEFRLevel.UNKNOWN not in dist or dist.get(CEFRLevel.UNKNOWN, 0) == 0
        assert sum(dist.values()) == pytest.approx(1.0)
        assert dist.get(CEFRLevel.A1, 0) > dist.get(CEFRLevel.C1, 0)
