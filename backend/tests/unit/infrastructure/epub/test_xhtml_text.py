from __future__ import annotations

import pytest
from backend.infrastructure.epub.xhtml_text import XhtmlTextExtractor

from tests.unit.infrastructure.epub.epub_builder import page


def paragraphs(body: str) -> list[str]:
    return [block.text for block in XhtmlTextExtractor().extract(page(body)).blocks]


@pytest.mark.unit
class TestXhtmlTextExtractor:
    def test_splits_text_into_paragraphs(self) -> None:
        assert paragraphs("<p>First  one.</p>\n<div><p>Second\n one.</p></div>") == [
            "First one.",
            "Second one.",
        ]

    def test_keeps_inline_markup_inside_words(self) -> None:
        assert paragraphs('<p><span class="drop">T</span>he <i>quick</i> fox</p>') == [
            "The quick fox"
        ]

    def test_breaks_lines_of_verse(self) -> None:
        assert paragraphs("<p>Roses are red,<br/>violets are blue</p>") == [
            "Roses are red,",
            "violets are blue",
        ]

    def test_drops_footnote_markers_but_keeps_ordinals(self) -> None:
        body = (
            '<p>Text<sup><a href="notes.xhtml#n1">1</a></sup> and more'
            '<a epub:type="noteref" href="#n2">[2]</a>, the 21<sup>st</sup> century.</p>'
        )
        assert paragraphs(body) == ["Text and more, the 21st century."]

    def test_drops_footnotes_scripts_and_hidden_text(self) -> None:
        body = (
            "<p>Story.</p><script>var x;</script><p hidden>secret</p>"
            '<p style="display: none">gone</p><aside epub:type="footnote"><p>A note.</p></aside>'
        )
        assert paragraphs(body) == ["Story."]

    def test_removes_soft_hyphens_and_non_breaking_spaces(self) -> None:
        assert paragraphs("<p>re­mark&#160;able</p>") == ["remark able"]

    def test_remembers_anchor_positions(self) -> None:
        document = XhtmlTextExtractor().extract(page('<p>a</p><h2 id="s1">Section</h2><p>b</p>'))
        assert document.anchors["s1"] == 1

    def test_reads_document_semantics_and_first_heading(self) -> None:
        document = XhtmlTextExtractor().extract(
            page(
                '<section epub:type="chapter"><h2>Title</h2><p>a</p></section>', 'role="doc-part"'
            ),
        )
        assert document.semantic_types == {"chapter", "part"}
        assert document.first_heading == "Title"

    def test_measures_link_share(self) -> None:
        document = XhtmlTextExtractor().extract(
            page('<p><a href="a.xhtml">abcd</a></p><p>efgh</p>')
        )
        assert document.link_ratio == 0.5
