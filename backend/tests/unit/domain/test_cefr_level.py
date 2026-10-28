import pytest
from backend.domain.value_objects.cefr_level import CEFRLevel


@pytest.mark.unit
class TestCEFRLevel:
    def test_values(self) -> None:
        assert CEFRLevel.A1.value == 1.0
        assert CEFRLevel.C2.value == 6.0
        assert CEFRLevel.UNKNOWN.value == 7.0

    def test_a_harder_word_is_learned(self) -> None:
        assert CEFRLevel.B2.is_learned_at(CEFRLevel.B1) is True
        assert CEFRLevel.C1.is_learned_at(CEFRLevel.B1) is True
        assert CEFRLevel.C2.is_learned_at(CEFRLevel.A1) is True

    def test_a_word_of_the_level_is_learned(self) -> None:
        assert CEFRLevel.B1.is_learned_at(CEFRLevel.B1) is True
        assert CEFRLevel.A1.is_learned_at(CEFRLevel.A1) is True

    def test_an_easier_word_is_not_learned(self) -> None:
        assert CEFRLevel.A1.is_learned_at(CEFRLevel.B1) is False
        assert CEFRLevel.A2.is_learned_at(CEFRLevel.B2) is False

    def test_a_word_of_no_known_level_is_always_learned(self) -> None:
        assert CEFRLevel.UNKNOWN.is_learned_at(CEFRLevel.C2) is True
        assert CEFRLevel.UNKNOWN.is_learned_at(CEFRLevel.A1) is True

    def test_easier_is_the_level_below(self) -> None:
        assert CEFRLevel.B2.easier() is CEFRLevel.B1
        assert CEFRLevel.A2.easier() is CEFRLevel.A1
        assert CEFRLevel.C2.easier() is CEFRLevel.C1

    def test_nothing_is_easier_than_a1(self) -> None:
        assert CEFRLevel.A1.easier() is CEFRLevel.A1

    def test_from_float_exact(self) -> None:
        assert CEFRLevel.from_float(1.0) is CEFRLevel.A1
        assert CEFRLevel.from_float(3.0) is CEFRLevel.B1
        assert CEFRLevel.from_float(6.0) is CEFRLevel.C2

    def test_from_float_rounds_to_nearest(self) -> None:
        assert CEFRLevel.from_float(2.8) is CEFRLevel.B1
        assert CEFRLevel.from_float(4.3) is CEFRLevel.B2

    def test_from_float_zero_returns_unknown(self) -> None:
        assert CEFRLevel.from_float(0) is CEFRLevel.UNKNOWN
        assert CEFRLevel.from_float(-1.0) is CEFRLevel.UNKNOWN

    def test_from_str_valid(self) -> None:
        assert CEFRLevel.from_str("B1") is CEFRLevel.B1
        assert CEFRLevel.from_str("c2") is CEFRLevel.C2
        assert CEFRLevel.from_str("  a1  ") is CEFRLevel.A1

    def test_from_str_invalid(self) -> None:
        with pytest.raises(ValueError, match="Invalid CEFR level"):
            CEFRLevel.from_str("X1")
