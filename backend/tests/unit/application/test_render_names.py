import pytest
from backend.application.use_cases.render_names import RenderNamesUseCase


@pytest.mark.unit
class TestRenderNames:
    def test_renders_in_order_without_collection(self) -> None:
        names = RenderNamesUseCase().execute("{{collection}} ch{{n}}", None, ["a", "b"])
        assert names == ["ch1", "ch2"]

    def test_renders_own_titles_with_collection(self) -> None:
        names = RenderNamesUseCase().execute("{{collection}}: {{title}}", "Dune", ["Desert"])
        assert names == ["Dune: Desert"]

    def test_bad_rule_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must contain"):
            RenderNamesUseCase().execute("{{collection}}", None, ["a"])

    def test_auto_numbers_pad_to_the_count(self) -> None:
        names = RenderNamesUseCase().execute("ch{{n}}", None, ["t"] * 11)
        assert names[0] == "ch01"
        assert names[10] == "ch11"

    def test_fixed_digits_pad_a_short_list(self) -> None:
        names = RenderNamesUseCase().execute("ch{{n}}", None, ["a", "b"], digits=3)
        assert names == ["ch001", "ch002"]
