"""A document's text in chunks of whole blocks, and the numbers of its list items."""
from __future__ import annotations

import pytest
from backend.domain.exceptions import TextBlockNotFoundError
from backend.domain.services import text_chunks as chunking
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.services.text_chunks import (
    LAST_BLOCK,
    TEXT_CHUNK_CHARS,
    TextChunk,
    block_bounds,
    chunk_at,
    chunk_with,
    list_numbers,
    text_chunks,
)
from backend.domain.value_objects.document import (
    BLOCK_SEPARATOR,
    Block,
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
    block_text,
)
from hypothesis import given, seed, settings
from hypothesis import strategies as st

MAX_BLOCKS = 60
MAX_BLOCK_CHARS = 3 * TEXT_CHUNK_CHARS


@st.composite
def _blocks(draw: st.DrawFn) -> Block:
    """A heading, paragraph or list item of up to MAX_BLOCK_CHARS characters."""
    length = draw(st.integers(0, MAX_BLOCK_CHARS))
    kind = draw(st.sampled_from(("heading", "paragraph", "list_item")))
    if kind == "heading":
        return Heading(draw(st.integers(1, 6)), "h" * length)
    cut = draw(st.integers(0, length))
    lines = (Line("a" * cut), Line("b" * (length - cut)))
    if kind == "paragraph":
        return Paragraph(lines, draw(st.sampled_from(list(ParagraphMode))))
    return ListItem(lines, ordered=draw(st.booleans()), depth=draw(st.integers(0, 3)))


def _chunk_length(document: Document, chunk: TextChunk) -> int:
    texts = [block_text(b) for b in document.blocks[chunk.first_block:chunk.end_block]]
    return len(BLOCK_SEPARATOR.join(texts))


@seed(7)
@settings(deadline=None, max_examples=200)
@given(st.lists(_blocks(), max_size=MAX_BLOCKS))
def test_chunks_hold_every_block_whole_in_order(blocks: list[Block]) -> None:
    document = Document(tuple(blocks))

    chunks = text_chunks(document)

    if not blocks:
        assert chunks == ()
        return
    assert chunks[0].first_block == 0
    assert chunks[-1].end_block == len(blocks)
    for chunk, after in zip(chunks, chunks[1:], strict=False):
        assert chunk.end_block == after.first_block
    assert all(chunk.first_block < chunk.end_block for chunk in chunks)
    assert tuple(
        block for chunk in chunks
        for block in document.blocks[chunk.first_block:chunk.end_block]
    ) == document.blocks
    assert all(
        _chunk_length(document, chunk) <= TEXT_CHUNK_CHARS
        or chunk.end_block - chunk.first_block == 1
        for chunk in chunks
    )
    # A chunk stops only where the next block would not fit.
    assert all(
        _chunk_length(document, TextChunk(chunk.first_block, chunk.end_block + 1))
        > TEXT_CHUNK_CHARS
        for chunk in chunks[:-1]
    )


@seed(7)
@settings(deadline=None, max_examples=100)
@given(st.lists(_blocks(), max_size=MAX_BLOCKS))
def test_block_bounds_are_where_the_blocks_stand_in_the_text(blocks: list[Block]) -> None:
    document = Document(tuple(blocks))
    text = DocumentLayout(document).text

    bounds = block_bounds(document)

    assert [text[start:end] for start, end in bounds] == [block_text(b) for b in blocks]


def _paragraph(length: int) -> Paragraph:
    return Paragraph((Line("x" * length),), ParagraphMode.FLOW)


# Three chunks: blocks 0-1, 2 (too long alone), 3-4.
HALF = TEXT_CHUNK_CHARS // 2 - len(BLOCK_SEPARATOR)
DOCUMENT = Document((
    _paragraph(HALF), _paragraph(HALF), _paragraph(TEXT_CHUNK_CHARS + 1),
    _paragraph(10), _paragraph(10),
))
CHUNKS = text_chunks(DOCUMENT)


def test_a_block_longer_than_a_chunk_is_a_chunk_of_its_own() -> None:
    assert text_chunks(DOCUMENT) == (TextChunk(0, 2), TextChunk(2, 3), TextChunk(3, 5))


@pytest.mark.parametrize(("block", "chunk"), [
    (0, TextChunk(0, 2)),
    (1, TextChunk(0, 2)),
    (2, TextChunk(2, 3)),
    (3, TextChunk(3, 5)),
    (4, TextChunk(3, 5)),
    (LAST_BLOCK, TextChunk(3, 5)),
])
def test_the_chunk_with_a_block(block: int, chunk: TextChunk) -> None:
    assert chunk_with(CHUNKS, block) == chunk


@pytest.mark.parametrize("block", [len(DOCUMENT.blocks), -2])
def test_a_block_outside_the_document_has_no_chunk(block: int) -> None:
    with pytest.raises(TextBlockNotFoundError):
        chunk_with(CHUNKS, block)


def test_an_empty_document_has_no_chunks_not_even_the_last() -> None:
    assert text_chunks(Document(())) == ()
    with pytest.raises(TextBlockNotFoundError):
        chunk_with((), LAST_BLOCK)


BOUNDS = block_bounds(DOCUMENT)
TEXT_LENGTH = len(DOCUMENT.text)


@pytest.mark.parametrize(("offset", "chunk"), [
    (-5, TextChunk(0, 2)),
    (0, TextChunk(0, 2)),
    (BOUNDS[1][1] - 1, TextChunk(0, 2)),
    # The blank line between the chunks belongs to the block before it.
    (BOUNDS[1][1], TextChunk(0, 2)),
    (BOUNDS[2][0], TextChunk(2, 3)),
    (BOUNDS[2][1] - 1, TextChunk(2, 3)),
    (BOUNDS[3][0], TextChunk(3, 5)),
    (TEXT_LENGTH - 1, TextChunk(3, 5)),
    (TEXT_LENGTH + 1_000, TextChunk(3, 5)),
])
def test_the_chunk_at_a_character_offset(offset: int, chunk: TextChunk) -> None:
    assert chunk_at(CHUNKS, BOUNDS, offset) == chunk


@seed(7)
@settings(deadline=None, max_examples=100)
@given(st.lists(_blocks(), min_size=1, max_size=MAX_BLOCKS), st.data())
def test_the_chunk_at_an_offset_holds_the_block_of_that_character(
    blocks: list[Block], data: st.DataObject,
) -> None:
    document = Document(tuple(blocks))
    bounds = block_bounds(document)
    offset = data.draw(st.integers(0, max(0, len(document.text) - 1)))
    block = max(i for i, (start, _) in enumerate(bounds) if start <= offset)

    chunk = chunk_at(text_chunks(document), bounds, offset)

    assert chunk.first_block <= block < chunk.end_block


def test_an_empty_document_has_no_chunk_at_any_offset() -> None:
    with pytest.raises(TextBlockNotFoundError):
        chunk_at((), (), 0)


def test_the_limit_is_read_when_the_chunks_are_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chunking, "TEXT_CHUNK_CHARS", 10)

    assert len(text_chunks(DOCUMENT)) == len(DOCUMENT.blocks)


# --- list numbers, as the review screen's list markers counted them ---------------------

def _item(depth: int, *, ordered: bool = True) -> ListItem:
    return ListItem((Line("item"),), ordered=ordered, depth=depth)


PARAGRAPH = _paragraph(4)


@pytest.mark.parametrize(("blocks", "numbers"), [
    pytest.param(
        [_item(0), _item(0), _item(1), _item(1), _item(0)], [1, 2, 1, 2, 3], id="nested",
    ),
    pytest.param(
        [_item(0), _item(0), PARAGRAPH, _item(0)], [1, 2, None, 1], id="reset-after-paragraph",
    ),
    pytest.param(
        [Heading(1, "Title"), _item(0), _item(0)], [None, 1, 2], id="after-heading",
    ),
    pytest.param(
        [_item(0), _item(2), _item(1), _item(2), _item(0)], [1, 1, 1, 1, 2],
        id="deeper-then-shallower",
    ),
    pytest.param(
        [_item(0), _item(1), _item(1), _item(0), _item(1)], [1, 1, 2, 2, 1],
        id="back-to-shallower-forgets-deeper",
    ),
    pytest.param(
        [_item(0, ordered=False), _item(0), _item(0, ordered=False)], [1, 2, 3],
        id="ordered-and-unordered",
    ),
])
def test_list_numbers(blocks: list[Block], numbers: list[int | None]) -> None:
    assert list_numbers(blocks) == tuple(numbers)
