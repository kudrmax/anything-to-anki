from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.get_bootstrap_words import GetBootstrapWordsUseCase
from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.value_objects.cefr_level import CEFRLevel


def _entry(lemma: str, cefr: CEFRLevel, zipf: float) -> BootstrapWordEntry:
    return BootstrapWordEntry(lemma=lemma, cefr_level=cefr, zipf_value=zipf)


@pytest.mark.unit
class TestGetBootstrapWordsUseCase:
    def setup_method(self) -> None:
        self.index_repo = MagicMock()
        self.known_word_repo = MagicMock()
        self.settings_repo = MagicMock()
        self.use_case = GetBootstrapWordsUseCase(
            index_repo=self.index_repo,
            known_word_repo=self.known_word_repo,
            settings_repo=self.settings_repo,
        )

    def test_computes_grid_levels_from_settings(self) -> None:
        """User CEFR=B1 -> grid={B2, C1, C2}."""
        self.settings_repo.get.return_value = "B1"
        self.known_word_repo.get_all_pairs.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
            _entry("run", CEFRLevel.A1, 5.2),
        ]

        result = self.use_case.execute(excluded_lemmas=[])

        lemmas = {w.lemma for w in result}
        assert "elaborate" in lemmas
        assert "nuance" in lemmas
        assert "run" not in lemmas

    def test_grid_shrinks_for_high_cefr(self) -> None:
        """User CEFR=B2 -> grid={C1, C2}."""
        self.settings_repo.get.return_value = "B2"
        self.known_word_repo.get_all_pairs.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]

        result = self.use_case.execute(excluded_lemmas=[])

        lemmas = {w.lemma for w in result}
        assert "elaborate" not in lemmas
        assert "nuance" in lemmas

    def test_excludes_known_words(self) -> None:
        self.settings_repo.get.return_value = "B1"
        self.known_word_repo.get_all_pairs.return_value = {("elaborate", None)}
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]

        result = self.use_case.execute(excluded_lemmas=[])

        lemmas = {w.lemma for w in result}
        assert "elaborate" not in lemmas

    def test_passes_excluded_lemmas(self) -> None:
        self.settings_repo.get.return_value = "B1"
        self.known_word_repo.get_all_pairs.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]

        result = self.use_case.execute(excluded_lemmas=["elaborate"])

        lemmas = {w.lemma for w in result}
        assert "elaborate" not in lemmas

    def test_returns_bootstrap_word_dtos(self) -> None:
        self.settings_repo.get.return_value = "B1"
        self.known_word_repo.get_all_pairs.return_value = set()
        self.index_repo.get_all_entries.return_value = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]

        result = self.use_case.execute(excluded_lemmas=[])

        assert len(result) == 1
        dto = result[0]
        assert dto.lemma == "elaborate"
        assert dto.cefr_level == "B2"
        assert dto.zipf_value == 3.8
