import pytest
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.adapters.cambridge.models import (
    CambridgeEntry,
    CambridgeSense,
    CambridgeWord,
)
from backend.infrastructure.adapters.cambridge.usage_lookup import CambridgeUsageLookup


def _sense(usages: list[str] | None = None) -> CambridgeSense:
    return CambridgeSense(
        definition="test",
        level="",
        examples=[],
        labels_and_codes=[],
        usages=usages or [],
        domains=[],
        regions=[],
        image_link="",
    )


def _word(pos: list[str], senses: list[CambridgeSense]) -> CambridgeWord:
    return CambridgeWord(
        word="test",
        entries=[CambridgeEntry(
            headword="test",
            pos=pos,
            uk_ipa=[], us_ipa=[],
            uk_audio=[], us_audio=[],
            senses=senses,
        )],
    )


@pytest.mark.unit
class TestCambridgeUsageLookup:
    def test_word_not_in_cambridge(self) -> None:
        lookup = CambridgeUsageLookup.from_data({})
        result = lookup.get_distribution("missing", "NN")
        assert result.groups is None

    def test_all_senses_no_usages(self) -> None:
        data = {"cool": _word(["adjective"], [_sense(), _sense()])}
        lookup = CambridgeUsageLookup.from_data(data)
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups == {"neutral": 1.0}

    def test_mixed_usages(self) -> None:
        data = {"cool": _word(["adjective"], [
            _sense(),
            _sense(),
            _sense(),
            _sense(["informal"]),
            _sense(["slang"]),
        ])}
        lookup = CambridgeUsageLookup.from_data(data)
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups is not None
        assert abs(result.groups["neutral"] - 0.6) < 0.01
        assert abs(result.groups["informal"] - 0.4) < 0.01

    def test_all_informal(self) -> None:
        data = {"gonna": _word(["verb"], [
            _sense(["informal"]),
            _sense(["very informal"]),
        ])}
        lookup = CambridgeUsageLookup.from_data(data)
        result = lookup.get_distribution("gonna", "VB")
        assert result.groups == {"informal": 1.0}

    def test_pos_filtering(self) -> None:
        data = {"cool": CambridgeWord(
            word="cool",
            entries=[
                CambridgeEntry(
                    headword="cool", pos=["adjective"],
                    uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                    senses=[_sense(["informal"])],
                ),
                CambridgeEntry(
                    headword="cool", pos=["noun"],
                    uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                    senses=[_sense()],
                ),
            ],
        )}
        lookup = CambridgeUsageLookup.from_data(data)
        result = lookup.get_distribution("cool", "JJ")
        assert result.groups == {"informal": 1.0}

    def test_pos_fallback_all_entries(self) -> None:
        data = {"cool": CambridgeWord(
            word="cool",
            entries=[
                CambridgeEntry(
                    headword="cool", pos=["adjective"],
                    uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                    senses=[_sense(["informal"])],
                ),
                CambridgeEntry(
                    headword="cool", pos=["noun"],
                    uk_ipa=[], us_ipa=[], uk_audio=[], us_audio=[],
                    senses=[_sense()],
                ),
            ],
        )}
        lookup = CambridgeUsageLookup.from_data(data)
        result = lookup.get_distribution("cool", "XX")
        assert result.groups is not None
        assert abs(result.groups["informal"] - 0.5) < 0.01
        assert abs(result.groups["neutral"] - 0.5) < 0.01

    def test_sense_with_multiple_usages(self) -> None:
        data = {"word": _word(["noun"], [
            _sense(["formal", "disapproving"]),
        ])}
        lookup = CambridgeUsageLookup.from_data(data)
        result = lookup.get_distribution("word", "NN")
        assert result.groups is not None
        assert len(result.groups) == 1

    def test_unknown_usage_label_treated_as_neutral(self) -> None:
        data = {"word": _word(["noun"], [_sense(["some_weird_label"])])}
        lookup = CambridgeUsageLookup.from_data(data)
        result = lookup.get_distribution("word", "NN")
        assert result.groups == {"neutral": 1.0}

    def test_case_insensitive_lemma(self) -> None:
        data = {"hello": _word(["noun"], [_sense(["informal"])])}
        lookup = CambridgeUsageLookup.from_data(data)
        result = lookup.get_distribution("Hello", "NN")
        assert result.groups == {"informal": 1.0}
