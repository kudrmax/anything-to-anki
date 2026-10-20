import pytest
from backend.domain.value_objects.number_format import NumberFormat


@pytest.mark.unit
class TestNumberFormat:
    @pytest.mark.parametrize(("total", "width"), [(6, 1), (11, 2), (120, 3), (1000, 4)])
    def test_auto_pads_to_the_count(self, total: int, width: int) -> None:
        assert NumberFormat().width(total) == width

    def test_fixed_digits_pad_whatever_the_count(self) -> None:
        assert NumberFormat(digits=2).width(6) == 2

    def test_one_digit_adds_no_zeros_to_a_long_list(self) -> None:
        assert NumberFormat(digits=1).width(13) == 1

    def test_digits_start_at_one(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            NumberFormat(digits=0)
