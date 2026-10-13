from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.epub import EpubError, EpubReader

from tests.unit.infrastructure.epub.epub_builder import EpubBuilder, TocLink, page, prose

if TYPE_CHECKING:
    from pathlib import Path


def chapter_page(title: str, words: int, anchor: str = "") -> str:
    anchor_attr = f' id="{anchor}"' if anchor else ""
    return page(f"<h1{anchor_attr}>{title}</h1><p>{prose(words)}</p>")


@pytest.mark.unit
class TestEpubReader:
    def test_reads_title_and_chapters_from_the_contents(self, tmp_path: Path) -> None:
        book = EpubBuilder(title="Ender's Game")
        book.add("ch1.xhtml", chapter_page("One", 300)).add("ch2.xhtml", chapter_page("Two", 400))
        book.nav = [TocLink("Chapter One", "ch1.xhtml"), TocLink("Chapter Two", "ch2.xhtml")]

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert result.title == "Ender's Game"
        assert [c.title for c in result.chapters] == ["Chapter One", "Chapter Two"]
        assert [c.word_count for c in result.chapters] == [301, 401]
        assert result.chapters[0].text.startswith("One\n\nword worda")

    def test_skips_cover_copyright_and_contents(self, tmp_path: Path) -> None:
        book = EpubBuilder()
        book.add("cover.xhtml", page("<p>Cover</p>", 'epub:type="cover"'))
        book.add("copy.xhtml", page(f"<p>{prose(150)} ISBN 978-0-00 All rights reserved.</p>"))
        book.add(
            "toc.xhtml",
            page("".join(f'<p><a href="ch1.xhtml">Chapter {i}</a></p>' for i in range(8))),
        )
        book.add("ch1.xhtml", chapter_page("One", 300))
        book.nav = [
            TocLink("Cover", "cover.xhtml"),
            TocLink("Copyright", "copy.xhtml"),
            TocLink("Contents", "toc.xhtml"),
            TocLink("Chapter One", "ch1.xhtml"),
        ]

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert [c.title for c in result.chapters] == ["Chapter One"]

    def test_drops_short_title_and_dedication_pages_before_the_contents(
        self, tmp_path: Path
    ) -> None:
        book = EpubBuilder()
        book.add("title.xhtml", page("<p>The Author</p><p>The Book</p><p>For my mother</p>"))
        book.add("ch1.xhtml", chapter_page("One", 300))
        book.nav = [TocLink("One", "ch1.xhtml")]

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert [c.title for c in result.chapters] == ["One"]

    def test_cuts_parts_into_chapters_but_keeps_sections_inside_chapters(
        self, tmp_path: Path
    ) -> None:
        book = EpubBuilder()
        book.add("part1.xhtml", page("<h1>Part One</h1>"))
        book.add(
            "ch1.xhtml",
            page(
                f'<h1>One</h1><p>{prose(9000)}</p><h2 id="s1">Section</h2><p>{prose(9000)}</p>',
            ),
        )
        book.add("ch2.xhtml", chapter_page("Two", 9000))
        book.add("part2.xhtml", page("<h1>Part Two</h1>"))
        book.add("ch3.xhtml", chapter_page("Three", 9000))
        book.ncx = [
            TocLink(
                "Part One",
                "part1.xhtml",
                [
                    TocLink("One", "ch1.xhtml", [TocLink("Section", "ch1.xhtml#s1")]),
                    TocLink("Two", "ch2.xhtml"),
                ],
            ),
            TocLink("Part Two", "part2.xhtml", [TocLink("Three", "ch3.xhtml")]),
        ]

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert [c.title for c in result.chapters] == ["One", "Two", "Three"]
        assert result.chapters[0].word_count == 18002

    def test_cuts_one_file_book_at_its_anchors(self, tmp_path: Path) -> None:
        body = "".join(f'<h2 id="c{i}">Chapter {i}</h2><p>{prose(200)}</p>' for i in range(1, 4))
        book = EpubBuilder().add("book.xhtml", page(body))
        book.nav = [TocLink(f"Chapter {i}", f"book.xhtml#c{i}") for i in range(1, 4)]

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert [c.title for c in result.chapters] == ["Chapter 1", "Chapter 2", "Chapter 3"]

    def test_starts_chapter_at_its_title_when_contents_point_near_it(self, tmp_path: Path) -> None:
        book = EpubBuilder()
        book.add(
            "a.xhtml",
            page(
                f'<p>{prose(300)}</p><p id="p1">{prose(200, "tail")}</p>'
                f"<p>Second Chapter</p><p>{prose(300)}</p>",
            ),
        )
        book.nav = [TocLink("1. First", "a.xhtml"), TocLink("2. Second Chapter", "a.xhtml#p1")]

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert result.chapters[1].text.startswith("Second Chapter\n\n")
        assert "tail" in result.chapters[0].text

    def test_moves_chapter_start_past_stray_lines_before_a_file_break(
        self, tmp_path: Path
    ) -> None:
        book = EpubBuilder()
        book.add("a.xhtml", page(f'<p>{prose(300)}</p><p id="pos">“A short quote.”</p>'))
        book.add("b.xhtml", page(f"<p>Untitled start {prose(300)}</p>"))
        book.nav = [TocLink("First", "a.xhtml"), TocLink("Second", "a.xhtml#pos")]

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert result.chapters[0].text.endswith("“A short quote.”")
        assert result.chapters[1].text.startswith("Untitled start")

    def test_splits_by_files_when_there_are_no_contents(self, tmp_path: Path) -> None:
        book = EpubBuilder()
        book.add("a.xhtml", chapter_page("Alpha", 200)).add("b.xhtml", chapter_page("Beta", 200))

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert [c.title for c in result.chapters] == ["Alpha", "Beta"]

    def test_reads_an_archive_without_container_and_package(self, tmp_path: Path) -> None:
        book = EpubBuilder(with_container=False, with_opf=False)
        book.add("a.html", chapter_page("Alpha", 200)).add("b.html", chapter_page("Beta", 200))

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        assert result.title is None
        assert [c.title for c in result.chapters] == ["Alpha", "Beta"]

    def test_reads_broken_markup(self, tmp_path: Path) -> None:
        markup = (
            f"<html><body><h1>One<p>{prose(120)}<p>{prose(100, 'next')}<div><b>bold</i></body>"
        )
        book = EpubBuilder().add("a.xhtml", markup)

        result = EpubReader().read(str(book.write(tmp_path / "b.epub")))

        paragraphs = result.chapters[0].text.split("\n\n")
        assert paragraphs[0] == "One"
        assert paragraphs[2].startswith("next nexta")
        assert paragraphs[3] == "bold"

    def test_rejects_a_file_that_is_not_an_archive(self, tmp_path: Path) -> None:
        path = tmp_path / "b.epub"
        path.write_text("not a zip")

        with pytest.raises(EpubError):
            EpubReader().read(str(path))

    def test_rejects_a_book_without_text(self, tmp_path: Path) -> None:
        path = tmp_path / "b.epub"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("a.xhtml", page('<img src="a.png"/>'))

        with pytest.raises(EpubError):
            EpubReader().read(str(path))
