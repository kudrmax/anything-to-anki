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
