import pytest
from backend.domain.services.inflected_forms import is_inflected_form


@pytest.mark.unit
class TestIsInflectedForm:
    @pytest.mark.parametrize(
        ("form", "base"),
        [
            ("terms", "term"),
            ("boxes", "box"),
            ("stories", "story"),
            ("carried", "carry"),
            ("playing", "play"),
            ("making", "make"),
            ("running", "run"),
            ("played", "play"),
            ("hoped", "hope"),
            ("stopped", "stop"),
            ("known", "know"),
            ("given", "give"),
            ("fallen", "fall"),
        ],
    )
    def test_a_form_of_a_known_base(self, form: str, base: str) -> None:
        assert is_inflected_form(form, {form, base})

    def test_not_a_form_without_its_base(self) -> None:
        assert not is_inflected_form("playing", {"playing"})

    def test_a_base_is_not_a_form_of_itself(self) -> None:
        assert not is_inflected_form("self", {"self", "sel"})

    def test_a_one_letter_stem_is_no_base(self) -> None:
        assert not is_inflected_form("as", {"as", "a"})
