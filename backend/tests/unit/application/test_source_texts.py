"""The laid-out documents kept between reads: by source and the fingerprint of its stored
document, bounded by their characters."""
from __future__ import annotations

from backend.application.utils.source_texts import SourceTexts
from backend.domain.value_objects.document import Document, Paragraph, ParagraphMode
from backend.domain.value_objects.document import Line as TextLine


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
    texts = SourceTexts(max_chars=10)
    first, second, long = _Reads("12345"), _Reads("67890"), _Reads("x" * 30)
    texts.of(1, "a", first)
    texts.of(2, "b", second)
    texts.of(1, "a", first)

    texts.of(3, "c", long)
    texts.of(3, "c", long)
    texts.of(1, "a", first)
    texts.of(2, "b", second)

    assert (first.count, second.count, long.count) == (2, 2, 1)
