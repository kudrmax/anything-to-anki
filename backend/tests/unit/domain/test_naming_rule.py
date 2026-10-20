import pytest
from backend.domain.value_objects.naming_rule import DEFAULT_NAMING_RULE, NamingRule


@pytest.mark.unit
class TestNamingRule:
    def test_default_names_by_collection_and_number(self) -> None:
        rule = NamingRule(DEFAULT_NAMING_RULE)
        assert rule.render("Atomic Habits", 3, "x") == "Atomic Habits ch3"

    def test_renders_own_title(self) -> None:
        assert NamingRule("{{title}}").render(None, 1, "How Memory Works") == "How Memory Works"

    def test_no_collection_collapses_spaces(self) -> None:
        assert NamingRule("{{collection}} ch{{n}}").render(None, 1, "x") == "ch1"

    def test_plain_text_with_number(self) -> None:
        assert NamingRule("AH part {{n}}").render("Atomic Habits", 2, "x") == "AH part 2"

    def test_rule_without_number_or_title_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must contain"):
            NamingRule("{{collection}} chapter")

    def test_number_is_padded_to_the_digits(self) -> None:
        assert NamingRule("ch{{n}}").render(None, 5, "x", digits=2) == "ch05"
