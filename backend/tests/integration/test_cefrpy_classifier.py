"""Integration test: VotingCEFRClassifier with all real sources."""
from __future__ import annotations

from pathlib import Path

import pytest
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cambridge.cefr_source import CambridgeCEFRSource
from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.efllex_cefr_source import EFLLexCEFRSource
from backend.infrastructure.adapters.kelly_cefr_source import KellyCEFRSource
from backend.infrastructure.adapters.oxford_cefr_source import OxfordCEFRSource

DATA_DIR = Path(__file__).resolve().parents[3] / "dictionaries" / "cefr"
CAMBRIDGE_DB_PATH = Path(__file__).resolve().parents[3] / "dictionaries" / "cambridge.db"


@pytest.mark.integration
class TestVotingCEFRClassifierIntegration:
    def setup_method(self) -> None:
        sources = [
            CefrpyCEFRSource(),
            EFLLexCEFRSource(DATA_DIR / "efllex.tsv"),
            OxfordCEFRSource(DATA_DIR / "oxford5000.csv"),
            KellyCEFRSource(DATA_DIR / "kelly.csv"),
        ]
        self.classifier = VotingCEFRClassifier(sources)

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
class TestVotingCEFRClassifierWithCambridgeIntegration:
    """Full integration: Cambridge priority + 4 fallback sources."""

    def setup_method(self) -> None:
        cambridge_cefr = CambridgeCEFRSource(CambridgeSQLiteReader(CAMBRIDGE_DB_PATH))
        sources = [
            CefrpyCEFRSource(),
            EFLLexCEFRSource(DATA_DIR / "efllex.tsv"),
            OxfordCEFRSource(DATA_DIR / "oxford5000.csv"),
            KellyCEFRSource(DATA_DIR / "kelly.csv"),
        ]
        self.classifier = VotingCEFRClassifier(
            sources, priority_source=cambridge_cefr
        )

    def test_common_word_uses_cambridge(self) -> None:
        """'happy' has Cambridge CEFR — should return a reasonable level."""
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
        """'and' is A2 in Cambridge — sanity check."""
        level = self.classifier.classify("and", "CC")
        assert level in (CEFRLevel.A1, CEFRLevel.A2)
