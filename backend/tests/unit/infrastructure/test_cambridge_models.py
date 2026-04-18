from __future__ import annotations

from backend.infrastructure.adapters.cambridge.models import (
    CambridgeEntry,
    CambridgeSense,
    CambridgeWord,
)


class TestCambridgeModels:
    def test_sense_is_frozen(self) -> None:
        sense = CambridgeSense(
            definition="a test",
            level="B1",
            examples=["example"],
            labels_and_codes=[],
            usages=[],
            domains=[],
            regions=[],
            image_link="",
        )
        assert sense.level == "B1"

    def test_entry_contains_senses(self) -> None:
        sense = CambridgeSense(
            definition="def",
            level="A1",
            examples=[],
            labels_and_codes=[],
            usages=[],
            domains=[],
            regions=[],
            image_link="",
        )
        entry = CambridgeEntry(
            headword="test",
            pos=["noun"],
            uk_ipa=[],
            us_ipa=[],
            uk_audio=[],
            us_audio=[],
            senses=[sense],
        )
        assert entry.senses[0].level == "A1"

    def test_word_contains_entries(self) -> None:
        word = CambridgeWord(word="test", entries=[])
        assert word.word == "test"
        assert word.entries == []
