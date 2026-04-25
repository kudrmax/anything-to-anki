import pytest

from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.services.bootstrap_word_selector import BootstrapWordSelector
from backend.domain.value_objects.cefr_level import CEFRLevel


def _entry(lemma: str, cefr: CEFRLevel, zipf: float) -> BootstrapWordEntry:
    return BootstrapWordEntry(lemma=lemma, cefr_level=cefr, zipf_value=zipf)


@pytest.mark.unit
class TestBootstrapWordSelector:
    def setup_method(self) -> None:
        self.selector = BootstrapWordSelector()

    def test_selects_one_word_per_cell(self) -> None:
        entries = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
            _entry("ubiquitous", CEFRLevel.C2, 3.1),
        ]
        grid_levels = {CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2}
        result = self.selector.select_words(entries, grid_levels, known_lemmas=set(), excluded_lemmas=set())
        lemmas = {w.lemma for w in result}
        assert lemmas == {"elaborate", "nuance", "ubiquitous"}

    def test_excludes_known_lemmas(self) -> None:
        entries = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]
        grid_levels = {CEFRLevel.B2, CEFRLevel.C1}
        result = self.selector.select_words(entries, grid_levels, known_lemmas={"elaborate"}, excluded_lemmas=set())
        lemmas = {w.lemma for w in result}
        assert lemmas == {"nuance"}

    def test_excludes_excluded_lemmas(self) -> None:
        entries = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("nuance", CEFRLevel.C1, 4.2),
        ]
        grid_levels = {CEFRLevel.B2, CEFRLevel.C1}
        result = self.selector.select_words(entries, grid_levels, known_lemmas=set(), excluded_lemmas={"elaborate"})
        lemmas = {w.lemma for w in result}
        assert lemmas == {"nuance"}

    def test_intersection_with_grid_levels(self) -> None:
        """Word with cefr_level outside grid is skipped."""
        entries = [
            _entry("run", CEFRLevel.A1, 5.2),
            _entry("elaborate", CEFRLevel.B2, 3.8),
        ]
        grid_levels = {CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2}
        result = self.selector.select_words(entries, grid_levels, known_lemmas=set(), excluded_lemmas=set())
        lemmas = {w.lemma for w in result}
        assert lemmas == {"elaborate"}

    def test_multi_cefr_lemma_takes_minimum_from_intersection(self) -> None:
        """Word 'elaborate' has B2 and C1. Grid={B2,C1,C2}. Min of intersection = B2."""
        entries = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("elaborate", CEFRLevel.C1, 3.8),
        ]
        grid_levels = {CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2}
        result = self.selector.select_words(entries, grid_levels, known_lemmas=set(), excluded_lemmas=set())
        assert len(result) == 1
        assert result[0].lemma == "elaborate"
        assert result[0].cefr_level == CEFRLevel.B2

    def test_one_word_per_cell_max(self) -> None:
        """Two words in same cell — only one returned."""
        entries = [
            _entry("elaborate", CEFRLevel.B2, 3.8),
            _entry("scrutinize", CEFRLevel.B2, 3.7),
        ]
        grid_levels = {CEFRLevel.B2}
        result = self.selector.select_words(entries, grid_levels, known_lemmas=set(), excluded_lemmas=set())
        assert len(result) == 1
        assert result[0].lemma in {"elaborate", "scrutinize"}

    def test_zipf_bands(self) -> None:
        """Words in different zipf bands go to different cells."""
        entries = [
            _entry("word_a", CEFRLevel.B2, 3.2),  # band [3.0, 3.5)
            _entry("word_b", CEFRLevel.B2, 3.7),  # band [3.5, 4.0)
            _entry("word_c", CEFRLevel.B2, 4.2),  # band [4.0, 4.5)
            _entry("word_d", CEFRLevel.B2, 4.7),  # band [4.5, 5.0)
            _entry("word_e", CEFRLevel.B2, 5.2),  # band [5.0, 5.5]
        ]
        grid_levels = {CEFRLevel.B2}
        result = self.selector.select_words(entries, grid_levels, known_lemmas=set(), excluded_lemmas=set())
        assert len(result) == 5
        lemmas = {w.lemma for w in result}
        assert lemmas == {"word_a", "word_b", "word_c", "word_d", "word_e"}

    def test_empty_entries_returns_empty(self) -> None:
        result = self.selector.select_words([], {CEFRLevel.B2}, known_lemmas=set(), excluded_lemmas=set())
        assert result == []

    def test_max_15_words(self) -> None:
        """3 CEFR levels x 5 zipf bands = 15 max."""
        entries = []
        for cefr in [CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2]:
            for i, zipf in enumerate([3.2, 3.7, 4.2, 4.7, 5.2]):
                entries.append(_entry(f"word_{cefr.name}_{i}", cefr, zipf))
        grid_levels = {CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2}
        result = self.selector.select_words(entries, grid_levels, known_lemmas=set(), excluded_lemmas=set())
        assert len(result) == 15
