from __future__ import annotations

import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource


@pytest.mark.integration
class TestCefrpyCEFRSource:
    def setup_method(self) -> None:
        self.source = CefrpyCEFRSource()

    def test_known_word_returns_single_level(self) -> None:
        dist = self.source.get_distribution("happy", "JJ")
        assert CEFRLevel.UNKNOWN not in dist or dist[CEFRLevel.UNKNOWN] == 0.0
        assert sum(dist.values()) == pytest.approx(1.0)
        max_level = max(dist, key=dist.get)  # type: ignore[arg-type]
        assert max_level in (CEFRLevel.A1, CEFRLevel.A2)

    def test_unknown_word_returns_unknown(self) -> None:
        dist = self.source.get_distribution("asdfghjkl", "NN")
        assert dist == {CEFRLevel.UNKNOWN: 1.0}

    def test_distribution_sums_to_one(self) -> None:
        dist = self.source.get_distribution("run", "VB")
        assert sum(dist.values()) == pytest.approx(1.0)
