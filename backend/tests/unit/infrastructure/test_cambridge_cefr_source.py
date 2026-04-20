from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cambridge.cefr_source import CambridgeCEFRSource
from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader

from .conftest import create_cambridge_test_db

if TYPE_CHECKING:
    from pathlib import Path


def _make_source(tmp_path: Path, entries: list[dict[str, object]]) -> CambridgeCEFRSource:
    db_path = create_cambridge_test_db(tmp_path, entries)
    reader = CambridgeSQLiteReader(db_path)
    return CambridgeCEFRSource(reader)


class TestCambridgeCEFRSource:
    def test_single_sense_single_level(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [
            {"word": "run", "pos": ["verb"], "senses": [{"level": "A1"}]},
        ])
        result = source.get_distribution("run", "VB")
        assert result == {CEFRLevel.A1: 1.0}

    def test_median_of_multiple_senses(self, tmp_path: Path) -> None:
        """[A1, A1, B1] -> median = A1 (index 1 of 3, lower-middle)."""
        source = _make_source(tmp_path, [
            {"word": "run", "pos": ["verb"], "senses": [
                {"level": "A1"}, {"level": "A1"}, {"level": "B1"},
            ]},
        ])
        result = source.get_distribution("run", "VB")
        assert result == {CEFRLevel.A1: 1.0}

    def test_median_even_count_picks_lower(self, tmp_path: Path) -> None:
        """[A1, B1, B2, C1] -> median of 4 = index 1 (lower-middle) = B1."""
        source = _make_source(tmp_path, [
            {"word": "go", "pos": ["verb"], "senses": [
                {"level": "A1"}, {"level": "B1"}, {"level": "B2"}, {"level": "C1"},
            ]},
        ])
        result = source.get_distribution("go", "VB")
        assert result == {CEFRLevel.B1: 1.0}

    def test_senses_without_level_ignored(self, tmp_path: Path) -> None:
        """Only senses with non-empty level participate in median."""
        source = _make_source(tmp_path, [
            {"word": "set", "pos": ["verb"], "senses": [
                {"level": ""}, {"level": "A2"}, {"level": ""},
                {"level": "C1"}, {"level": ""},
            ]},
        ])
        result = source.get_distribution("set", "VB")
        assert result == {CEFRLevel.A2: 1.0}

    def test_all_senses_without_level_returns_unknown(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [
            {"word": "hmm", "pos": ["exclamation"], "senses": [
                {"level": ""}, {"level": ""},
            ]},
        ])
        result = source.get_distribution("hmm", "UH")
        assert result == {CEFRLevel.UNKNOWN: 1.0}

    def test_word_not_in_dictionary_returns_unknown(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [])
        result = source.get_distribution("asdfghjkl", "NN")
        assert result == {CEFRLevel.UNKNOWN: 1.0}

    def test_pos_filter_matches_verb(self, tmp_path: Path) -> None:
        """VB should match entries with pos=['verb'], not pos=['noun']."""
        source = _make_source(tmp_path, [
            {"word": "light", "pos": ["noun"], "senses": [{"level": "B1"}]},
            {"word": "light", "pos": ["verb"], "senses": [{"level": "C1"}]},
        ])
        result = source.get_distribution("light", "VB")
        assert result == {CEFRLevel.C1: 1.0}

    def test_pos_filter_matches_adjective(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [
            {"word": "light", "pos": ["noun"], "senses": [{"level": "B1"}]},
            {"word": "light", "pos": ["adjective"], "senses": [{"level": "A2"}]},
        ])
        result = source.get_distribution("light", "JJ")
        assert result == {CEFRLevel.A2: 1.0}

    def test_pos_fallback_when_no_match(self, tmp_path: Path) -> None:
        """If no entry matches the POS, use all entries."""
        source = _make_source(tmp_path, [
            {"word": "light", "pos": ["noun"], "senses": [{"level": "B1"}]},
            {"word": "light", "pos": ["verb"], "senses": [{"level": "C1"}]},
        ])
        result = source.get_distribution("light", "MD")
        assert result == {CEFRLevel.B1: 1.0}

    def test_multiple_entries_levels_aggregated(self, tmp_path: Path) -> None:
        """Levels from all matching entries are combined for median."""
        source = _make_source(tmp_path, [
            {"word": "run", "pos": ["verb"], "senses": [
                {"level": "A1"}, {"level": "B2"},
            ]},
            {"word": "run", "pos": ["verb"], "senses": [{"level": "A1"}]},
        ])
        result = source.get_distribution("run", "VB")
        assert result == {CEFRLevel.A1: 1.0}

    def test_empty_dictionary_returns_unknown(self, tmp_path: Path) -> None:
        source = _make_source(tmp_path, [])
        result = source.get_distribution("anything", "NN")
        assert result == {CEFRLevel.UNKNOWN: 1.0}
