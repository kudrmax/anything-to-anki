from __future__ import annotations

import pytest
from backend.infrastructure.adapters.markdown_blocks import MarkdownBlockParser

pytestmark = pytest.mark.unit


def parse(markdown: str) -> list[str]:
    return [block.text for block in MarkdownBlockParser().parse(markdown)]


def test_headings_become_paragraphs_of_their_own() -> None:
    assert parse("# Chapter Digests\n## Preface ##\nText goes on.") == [
        "Chapter Digests", "Preface", "Text goes on.",
    ]


def test_setext_headings_lose_their_underline() -> None:
    assert parse("Title\n=====\n\nSection\n-------\nBody.") == ["Title", "Section", "Body."]


def test_emphasis_marks_are_removed() -> None:
    assert parse("📌 **In short:** a *cautious* and __bold__ _plain_ ~~old~~ claim.") == [
        "📌 In short: a cautious and bold plain old claim.",
    ]


def test_marks_inside_words_are_kept() -> None:
    assert parse("snake_case_name and 2*3*4 stay") == ["snake_case_name and 2*3*4 stay"]


def test_list_items_become_paragraphs() -> None:
    markdown = (
        "**Summary:**\n\n1. **First point.** Details\ncontinue here.\n"
        "2) Second.\n- [x] Done task\n* Bullet"
    )
    assert parse(markdown) == [
        "Summary:", "First point. Details continue here.", "Second.", "Done task", "Bullet",
    ]


def test_hard_wrapped_paragraph_is_joined() -> None:
    assert parse("He opens by saying\nthat the book will help.") == [
        "He opens by saying that the book will help.",
    ]


def test_links_keep_their_text_and_images_go() -> None:
    markdown = (
        "See [the paper](https://x.org/p) and [docs][ref]. ![chart](c.png) <https://x.org>"
        "\n\n[ref]: https://x.org"
    )
    assert parse(markdown) == ["See the paper and docs."]


def test_code_rules_quotes_and_comments() -> None:
    markdown = (
        "---\ntitle: Notes\n---\n"
        "Intro `inline` text.\n\n```python\nprint('x')\n```\n\n***\n\n"
        "> A quoted\n> line.\n<!-- hidden -->\nAfter."
    )
    assert parse(markdown) == ["Intro inline text.", "A quoted line.", "After."]


def test_tables_give_their_cells() -> None:
    assert parse("| Word | Meaning |\n|---|:---:|\n| flourish | grow well |") == [
        "Word", "Meaning", "flourish", "grow well",
    ]


def test_footnotes_and_escapes() -> None:
    assert parse("A claim[^1] costs \\*nothing\\*.\n\n[^1]: The source.") == [
        "A claim costs *nothing*.", "The source.",
    ]
