from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.infrastructure.adapters.cambridge.parser import parse_cambridge_jsonl

if TYPE_CHECKING:
    from pathlib import Path


class TestParseCambridgeJsonl:
    def _write_jsonl(self, records: list[dict], path: Path) -> None:  # type: ignore[type-arg]
        with open(path, "w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

    def _make_record(
        self,
        word: str = "test",
        pos: list[str] | None = None,
        level: str = "B1",
    ) -> dict[str, object]:
        return {
            "word": word,
            "scraped_at": "2026-04-16T00:00:00+00:00",
            "entries": [
                {
                    "headword": word,
                    "pos": pos or ["noun"],
                    "uk_ipa": ["/test/"],
                    "us_ipa": ["/test/"],
                    "uk_audio": [],
                    "us_audio": [],
                    "senses": [
                        {
                            "definition": f"a {word}",
                            "level": level,
                            "examples": ["example sentence"],
                            "labels_and_codes": [],
                            "usages": [],
                            "domains": [],
                            "regions": [],
                            "image_link": "",
                        }
                    ],
                }
            ],
        }

    def test_parses_valid_record(self, tmp_path: Path) -> None:
        path = tmp_path / "cambridge.jsonl"
        self._write_jsonl([self._make_record("hello", level="A1")], path)
        result = parse_cambridge_jsonl(path)
        assert "hello" in result
        word = result["hello"]
        assert word.word == "hello"
        assert len(word.entries) == 1
        assert word.entries[0].pos == ["noun"]
        assert word.entries[0].senses[0].level == "A1"
        assert word.entries[0].senses[0].definition == "a hello"

    def test_parses_multiple_records(self, tmp_path: Path) -> None:
        path = tmp_path / "cambridge.jsonl"
        records = [self._make_record("one"), self._make_record("two")]
        self._write_jsonl(records, path)
        result = parse_cambridge_jsonl(path)
        assert len(result) == 2
        assert "one" in result
        assert "two" in result

    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.jsonl"
        result = parse_cambridge_jsonl(path)
        assert result == {}

    def test_empty_file_returns_empty_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        result = parse_cambridge_jsonl(path)
        assert result == {}

    def test_broken_line_skipped_rest_parsed(self, tmp_path: Path) -> None:
        path = tmp_path / "cambridge.jsonl"
        valid = json.dumps(self._make_record("good"))
        path.write_text(f'{valid}\n{{"broken json\n')
        result = parse_cambridge_jsonl(path)
        assert "good" in result
        assert len(result) >= 1

    def test_record_missing_entries_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "cambridge.jsonl"
        bad_record: dict[str, object] = {"word": "bad"}
        good_record = self._make_record("good")
        self._write_jsonl([bad_record, good_record], path)
        result = parse_cambridge_jsonl(path)
        assert "good" in result
        assert "bad" not in result

    def test_all_sense_fields_parsed(self, tmp_path: Path) -> None:
        path = tmp_path / "cambridge.jsonl"
        record: dict[str, object] = {
            "word": "rich",
            "scraped_at": "2026-04-16T00:00:00+00:00",
            "entries": [{
                "headword": "rich",
                "pos": ["adjective"],
                "uk_ipa": ["/rɪtʃ/"],
                "us_ipa": ["/rɪtʃ/"],
                "uk_audio": ["https://example.com/uk.mp3"],
                "us_audio": ["https://example.com/us.mp3"],
                "senses": [{
                    "definition": "having a lot of money",
                    "level": "A2",
                    "examples": ["a rich man"],
                    "labels_and_codes": ["C2"],
                    "usages": ["informal"],
                    "domains": ["FINANCE"],
                    "regions": ["UK"],
                    "image_link": "https://example.com/img.png",
                }],
            }],
        }
        self._write_jsonl([record], path)
        result = parse_cambridge_jsonl(path)
        sense = result["rich"].entries[0].senses[0]
        assert sense.definition == "having a lot of money"
        assert sense.level == "A2"
        assert sense.examples == ["a rich man"]
        assert sense.labels_and_codes == ["C2"]
        assert sense.usages == ["informal"]
        assert sense.domains == ["FINANCE"]
        assert sense.regions == ["UK"]
        assert sense.image_link == "https://example.com/img.png"

    def test_entry_audio_and_ipa_parsed(self, tmp_path: Path) -> None:
        path = tmp_path / "cambridge.jsonl"
        record = self._make_record("test")
        self._write_jsonl([record], path)
        result = parse_cambridge_jsonl(path)
        entry = result["test"].entries[0]
        assert entry.uk_ipa == ["/test/"]
        assert entry.us_ipa == ["/test/"]
