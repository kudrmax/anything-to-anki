from __future__ import annotations

import pytest
from backend.infrastructure.adapters.regex_text_cleaner import RegexTextCleaner

pytestmark = pytest.mark.unit


def test_keeps_one_blank_line_between_paragraphs() -> None:
    text = "Summary:\n\n\n\n  Seligman calls for a revolution.  \n\nHe argues."
    assert RegexTextCleaner().clean(text) == (
        "Summary:\n\nSeligman calls for a revolution.\n\nHe argues."
    )


def test_keeps_lines_of_a_paragraph_together() -> None:
    assert RegexTextCleaner().clean("I told him that\n  we would come back") == (
        "I told him that\nwe would come back"
    )
