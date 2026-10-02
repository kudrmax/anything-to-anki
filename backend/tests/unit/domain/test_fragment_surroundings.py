import pytest
from backend.domain.value_objects.fragment_surroundings import FragmentSurroundings


@pytest.mark.unit
class TestFragmentSurroundings:
    def test_text_around_the_phrase(self) -> None:
        text = "Wow, you guys sure have a lot of books about being a lesbian. Well, you know."
        found = FragmentSurroundings.find(text, "of books about being a lesbian.", width=21)
        assert found == FragmentSurroundings(
            before="guys sure have a lot ", after=" Well, you know.",
        )

    def test_at_the_edges_of_the_text(self) -> None:
        found = FragmentSurroundings.find("Hold on.", "Hold on.")
        assert found == FragmentSurroundings(before="", after="")

    def test_phrase_missing_from_the_text(self) -> None:
        assert FragmentSurroundings.find("some text", "edited by hand") is None

    def test_empty_phrase(self) -> None:
        assert FragmentSurroundings.find("some text", "") is None
