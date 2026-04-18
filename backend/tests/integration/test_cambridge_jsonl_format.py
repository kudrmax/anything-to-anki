"""Validate the structure of the real cambridge.jsonl file.

If the scraper changes the output format, these tests catch it.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

CAMBRIDGE_PATH = Path(__file__).resolve().parents[3] / "dictionaries" / "cambridge.jsonl"

VALID_CEFR_LEVELS = {"", "A1", "A2", "B1", "B2", "C1", "C2"}
SAMPLE_SIZE = 200


@pytest.mark.integration
class TestCambridgeJsonlFormat:
    """Structural validation of cambridge.jsonl records."""

    @pytest.fixture(scope="class")
    def sampled_records(self) -> list[dict]:  # type: ignore[type-arg]
        if not CAMBRIDGE_PATH.exists():
            pytest.skip(f"cambridge.jsonl not found at {CAMBRIDGE_PATH}")

        all_lines: list[str] = []
        with open(CAMBRIDGE_PATH, encoding="utf-8") as f:
            all_lines = f.readlines()

        assert len(all_lines) > 0, "cambridge.jsonl is empty"

        sample = random.sample(all_lines, min(SAMPLE_SIZE, len(all_lines)))
        records = []
        for line in sample:
            line = line.strip()
            if line:
                records.append(json.loads(line))
        return records

    def test_top_level_fields(self, sampled_records: list[dict]) -> None:  # type: ignore[type-arg]
        for record in sampled_records:
            assert "word" in record, f"Missing 'word' field: {record.keys()}"
            assert isinstance(record["word"], str)
            assert "entries" in record, f"Missing 'entries' for word={record.get('word')}"
            assert isinstance(record["entries"], list)

    def test_entry_structure(self, sampled_records: list[dict]) -> None:  # type: ignore[type-arg]
        for record in sampled_records:
            for entry in record["entries"]:
                assert "headword" in entry
                assert isinstance(entry["headword"], str)
                assert "pos" in entry
                assert isinstance(entry["pos"], list)
                # pos can be empty for some word forms (e.g. "derided")
                assert "senses" in entry
                assert isinstance(entry["senses"], list)
                for field in ("uk_ipa", "us_ipa", "uk_audio", "us_audio"):
                    assert isinstance(entry.get(field, []), list), (
                        f"{field} should be list for {entry['headword']}"
                    )

    def test_sense_structure(self, sampled_records: list[dict]) -> None:  # type: ignore[type-arg]
        for record in sampled_records:
            for entry in record["entries"]:
                for sense in entry["senses"]:
                    assert "definition" in sense
                    assert isinstance(sense["definition"], str)
                    assert "level" in sense
                    assert sense["level"] in VALID_CEFR_LEVELS, (
                        f"Invalid CEFR level '{sense['level']}' "
                        f"in word={record['word']}"
                    )
                    assert isinstance(sense.get("examples", []), list)
                    assert isinstance(sense.get("usages", []), list)
                    assert isinstance(sense.get("domains", []), list)
                    assert isinstance(sense.get("regions", []), list)

    def test_has_words_with_cefr(self, sampled_records: list[dict]) -> None:  # type: ignore[type-arg]
        """At least some records should have CEFR levels — sanity check."""
        has_cefr = False
        for record in sampled_records:
            for entry in record["entries"]:
                for sense in entry["senses"]:
                    if sense.get("level") in {"A1", "A2", "B1", "B2", "C1", "C2"}:
                        has_cefr = True
                        break
        assert has_cefr, "No CEFR levels found in sample — data may be broken"
