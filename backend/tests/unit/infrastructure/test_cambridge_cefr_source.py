from __future__ import annotations

from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.infrastructure.adapters.cambridge.cefr_source import CambridgeCEFRSource
from backend.infrastructure.adapters.cambridge.models import (
    CambridgeEntry,
    CambridgeSense,
    CambridgeWord,
)


def _sense(level: str = "", definition: str = "def") -> CambridgeSense:
    return CambridgeSense(
        definition=definition,
        level=level,
        examples=[],
        labels_and_codes=[],
        usages=[],
        domains=[],
        regions=[],
        image_link="",
    )


def _entry(
    pos: list[str] | None = None,
    levels: list[str] | None = None,
) -> CambridgeEntry:
    pos = pos or ["noun"]
    levels = levels or ["B1"]
    return CambridgeEntry(
        headword="test",
        pos=pos,
        uk_ipa=[],
        us_ipa=[],
        uk_audio=[],
        us_audio=[],
        senses=[_sense(level=lvl) for lvl in levels],
    )


def _word(
    word: str,
    entries: list[CambridgeEntry] | None = None,
) -> CambridgeWord:
    return CambridgeWord(word=word, entries=entries or [])


class TestCambridgeCEFRSource:
    def test_single_sense_single_level(self) -> None:
        data = {"run": _word("run", [_entry(pos=["verb"], levels=["A1"])])}
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("run", "VB")
        assert result == {CEFRLevel.A1: 1.0}

    def test_median_of_multiple_senses(self) -> None:
        """[A1, A1, B1] -> median = A1 (index 1 of 3, lower-middle)."""
        data = {"run": _word("run", [_entry(pos=["verb"], levels=["A1", "A1", "B1"])])}
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("run", "VB")
        assert result == {CEFRLevel.A1: 1.0}

    def test_median_even_count_picks_lower(self) -> None:
        """[A1, B1, B2, C1] -> median of 4 = index 1 (lower-middle) = B1."""
        data = {"go": _word("go", [_entry(pos=["verb"], levels=["A1", "B1", "B2", "C1"])])}
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("go", "VB")
        assert result == {CEFRLevel.B1: 1.0}

    def test_senses_without_level_ignored(self) -> None:
        """Only senses with non-empty level participate in median."""
        data = {"set": _word("set", [_entry(pos=["verb"], levels=["", "A2", "", "C1", ""])])}
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("set", "VB")
        assert result == {CEFRLevel.A2: 1.0}

    def test_all_senses_without_level_returns_unknown(self) -> None:
        data = {"hmm": _word("hmm", [_entry(pos=["exclamation"], levels=["", ""])])}
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("hmm", "UH")
        assert result == {CEFRLevel.UNKNOWN: 1.0}

    def test_word_not_in_dictionary_returns_unknown(self) -> None:
        source = CambridgeCEFRSource({})
        result = source.get_distribution("asdfghjkl", "NN")
        assert result == {CEFRLevel.UNKNOWN: 1.0}

    def test_pos_filter_matches_verb(self) -> None:
        """VB should match entries with pos=['verb'], not pos=['noun']."""
        data = {
            "light": _word("light", [
                _entry(pos=["noun"], levels=["B1"]),
                _entry(pos=["verb"], levels=["C1"]),
            ])
        }
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("light", "VB")
        assert result == {CEFRLevel.C1: 1.0}

    def test_pos_filter_matches_adjective(self) -> None:
        data = {
            "light": _word("light", [
                _entry(pos=["noun"], levels=["B1"]),
                _entry(pos=["adjective"], levels=["A2"]),
            ])
        }
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("light", "JJ")
        assert result == {CEFRLevel.A2: 1.0}

    def test_pos_fallback_when_no_match(self) -> None:
        """If no entry matches the POS, use all entries."""
        data = {
            "light": _word("light", [
                _entry(pos=["noun"], levels=["B1"]),
                _entry(pos=["verb"], levels=["C1"]),
            ])
        }
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("light", "MD")
        assert result == {CEFRLevel.B1: 1.0}

    def test_multiple_entries_levels_aggregated(self) -> None:
        """Levels from all matching entries are combined for median."""
        data = {
            "run": _word("run", [
                _entry(pos=["verb"], levels=["A1", "B2"]),
                _entry(pos=["verb"], levels=["A1"]),
            ])
        }
        source = CambridgeCEFRSource(data)
        result = source.get_distribution("run", "VB")
        assert result == {CEFRLevel.A1: 1.0}

    def test_empty_dictionary_returns_unknown(self) -> None:
        source = CambridgeCEFRSource({})
        result = source.get_distribution("anything", "NN")
        assert result == {CEFRLevel.UNKNOWN: 1.0}
