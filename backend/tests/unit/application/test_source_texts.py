"""The laid-out documents kept between reads: by source and the fingerprint of its stored
document, bounded by the memory they take."""
from __future__ import annotations

import gc
import tracemalloc
from typing import TYPE_CHECKING

import pytest
from backend.application.utils.source_texts import SourceText, SourceTexts
from backend.domain.value_objects.document import Document, Heading, Paragraph, ParagraphMode
from backend.domain.value_objects.document import Line as TextLine

if TYPE_CHECKING:
    from collections.abc import Callable


def _document(text: str) -> Document:
    return Document((Paragraph((TextLine(text),), ParagraphMode.FLOW),))


class _Reads:
    """A document read from the store, counted."""

    def __init__(self, text: str) -> None:
        self.document = _document(text)
        self.count = 0

    def __call__(self) -> Document:
        self.count += 1
        return self.document


def test_a_source_is_laid_out_once_while_its_fingerprint_stays() -> None:
    texts = SourceTexts()
    read = _Reads("Once upon a time.")

    first = texts.of(1, "a", read)
    again = texts.of(1, "a", read)

    assert again is first
    assert read.count == 1
    assert first.layout.text == "Once upon a time."


def test_another_fingerprint_under_the_same_source_is_laid_out_anew() -> None:
    texts = SourceTexts()
    texts.of(1, "deleted", _Reads("The source deleted since."))

    reused = texts.of(1, "new", _Reads("A new source with its id."))

    assert reused.layout.text == "A new source with its id."


def test_the_texts_read_longest_ago_go_first_and_the_last_one_stays() -> None:
    texts = SourceTexts(max_bytes=2 * SourceText.of(_document("12345")).size)
    first, second, long = _Reads("12345"), _Reads("67890"), _Reads("x" * 30)
    texts.of(1, "a", first)
    texts.of(2, "b", second)
    texts.of(1, "a", first)

    texts.of(3, "c", long)
    texts.of(3, "c", long)
    texts.of(1, "a", first)
    texts.of(2, "b", second)

    assert (first.count, second.count, long.count) == (2, 2, 1)


PROSE = "He gave up the relentless pursuit of happiness, and the rain kept on falling."


def _prose() -> Document:
    return Document(tuple(
        Paragraph(tuple(TextLine(f"{PROSE} {i} {k}") for k in range(3)), ParagraphMode.FLOW)
        for i in range(1500)
    ))


def _lyrics() -> Document:
    return Document(tuple(
        Paragraph(tuple(TextLine(f"la love {i} {k}") for k in range(4)), ParagraphMode.LINES)
        for i in range(2000)
    ))


def _subtitles() -> Document:
    return Document(tuple(
        Paragraph((TextLine(f"I told him {i}", start_ms=i, end_ms=i + 1),), ParagraphMode.FLOW)
        for i in range(4000)
    ))


def _headings() -> Document:
    return Document(tuple(Heading(2, f"Chapter {i}") for i in range(4000)))


@pytest.mark.parametrize("make", [_prose, _lyrics, _subtitles, _headings])
def test_the_size_of_a_laid_out_text_is_at_least_the_memory_it_takes(
    make: Callable[[], Document],
) -> None:
    gc.collect()
    tracemalloc.start()
    try:
        text = SourceText.of(make())
        taken, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert taken <= text.size, f"{taken} bytes taken, {text.size} estimated"
