from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.adapters.cambridge.sqlite_reader import CambridgeSQLiteReader
from backend.infrastructure.adapters.cambridge.usage_lookup import CambridgeUsageLookup

from .conftest import create_cambridge_test_db

if TYPE_CHECKING:
    from pathlib import Path


def _make_lookup(tmp_path: Path, entries: list[dict[str, object]]) -> CambridgeUsageLookup:
    db_path = create_cambridge_test_db(tmp_path, entries)
    reader = CambridgeSQLiteReader(db_path)
    return CambridgeUsageLookup(reader)


@pytest.mark.unit
class TestCambridgeUsageLookup:
    def test_word_not_in_cambridge(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [])
        result = lookup.get_distribution("missing", "NN")
        assert result.groups is None

    def test_all_senses_no_usages(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [
            {"word": "cool", "pos": ["adjective"], "senses": [
                {"usages": []}, {"usages": []},
            ]},
        ])
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups == {"neutral": 1.0}

    def test_mixed_usages(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [
            {"word": "cool", "pos": ["adjective"], "senses": [
                {"usages": []},
                {"usages": []},
                {"usages": []},
                {"usages": ["informal"]},
                {"usages": ["slang"]},
            ]},
        ])
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups is not None
        assert abs(result.groups["neutral"] - 0.6) < 0.01
        assert abs(result.groups["informal"] - 0.4) < 0.01

    def test_all_informal(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [
            {"word": "gonna", "pos": ["verb"], "senses": [
                {"usages": ["informal"]},
                {"usages": ["very informal"]},
            ]},
        ])
        result = lookup.get_distribution("gonna", "VB")
        assert result.groups == {"informal": 1.0}

    def test_pos_filtering(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [
            {"word": "cool", "pos": ["adjective"], "senses": [
                {"usages": ["informal"]},
            ]},
            {"word": "cool", "pos": ["noun"], "senses": [
                {"usages": []},
            ]},
        ])
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups == {"informal": 1.0}

    def test_pos_fallback_all_entries(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [
            {"word": "cool", "pos": ["adjective"], "senses": [
                {"usages": ["informal"]},
            ]},
            {"word": "cool", "pos": ["noun"], "senses": [
                {"usages": []},
            ]},
        ])
        result = lookup.get_distribution("cool", "XX")
        assert result.groups is not None
        assert abs(result.groups["informal"] - 0.5) < 0.01
        assert abs(result.groups["neutral"] - 0.5) < 0.01

    def test_sense_with_multiple_usages(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [
            {"word": "word", "pos": ["noun"], "senses": [
                {"usages": ["formal", "disapproving"]},
            ]},
        ])
        result = lookup.get_distribution("word", "NN")
        assert result.groups is not None
        assert len(result.groups) == 1

    def test_unknown_usage_label_treated_as_neutral(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [
            {"word": "word", "pos": ["noun"], "senses": [
                {"usages": ["some_weird_label"]},
            ]},
        ])
        result = lookup.get_distribution("word", "NN")
        assert result.groups == {"neutral": 1.0}

    def test_case_insensitive_lemma(self, tmp_path: Path) -> None:
        lookup = _make_lookup(tmp_path, [
            {"word": "hello", "pos": ["noun"], "senses": [
                {"usages": ["informal"]},
            ]},
        ])
        result = lookup.get_distribution("Hello", "NN")
        assert result.groups == {"informal": 1.0}
