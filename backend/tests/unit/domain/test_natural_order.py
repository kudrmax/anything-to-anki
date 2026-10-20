import pytest
from backend.domain.services.natural_order import natural_key


@pytest.mark.unit
class TestNaturalKey:
    def test_numbers_sort_by_value(self) -> None:
        assert sorted(["ch10", "ch2"], key=natural_key) == ["ch2", "ch10"]

    def test_superscript_digit_is_text_not_a_number(self) -> None:
        assert sorted(["1²2", "1a"], key=natural_key) == ["1a", "1²2"]
