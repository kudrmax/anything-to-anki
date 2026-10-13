import os

import pytest
from backend.application.utils.typed_path import normalize_typed_path

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("/books/Flourish (with digest).epub", "/books/Flourish (with digest).epub"),
        ("'/books/Flourish (with digest).epub'", "/books/Flourish (with digest).epub"),
        ('"/books/Flourish (with digest).epub"', "/books/Flourish (with digest).epub"),
        ("/books/Flourish\\ \\(with\\ digest\\).epub", "/books/Flourish (with digest).epub"),
        ("  /books/dune.epub \n", "/books/dune.epub"),
    ],
)
def test_path_copied_from_a_shell_points_to_the_file(typed: str, expected: str) -> None:
    assert normalize_typed_path(typed) == expected


def test_home_shortcut_is_expanded() -> None:
    home = os.path.expanduser("~")
    assert normalize_typed_path("~/dune.epub") == os.path.join(home, "dune.epub")


def test_quote_inside_a_name_is_kept() -> None:
    assert normalize_typed_path("/books/Ender's Game.epub") == "/books/Ender's Game.epub"
