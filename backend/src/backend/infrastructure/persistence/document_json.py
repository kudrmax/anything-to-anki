"""How a source document is stored: JSON with one object per block."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.domain.value_objects.document import (
    Block,
    Document,
    Heading,
    Line,
    ListItem,
    Paragraph,
    ParagraphMode,
)


class _LineJson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    start_ms: int | None = None
    end_ms: int | None = None


class _HeadingJson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["heading"] = "heading"
    level: int
    text: str


class _ParagraphJson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["paragraph"] = "paragraph"
    mode: ParagraphMode
    lines: list[_LineJson]


class _ListItemJson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["list_item"] = "list_item"
    ordered: bool
    depth: int
    lines: list[_LineJson]


class _DocumentJson(BaseModel):
    model_config = ConfigDict(extra="forbid")

    blocks: list[
        Annotated[_HeadingJson | _ParagraphJson | _ListItemJson, Field(discriminator="type")]
    ]


def dump_document(document: Document) -> str:
    stored = _DocumentJson(blocks=[_block_json(block) for block in document.blocks])
    return stored.model_dump_json(exclude_none=True)


def load_document(raw: str) -> Document:
    stored = _DocumentJson.model_validate_json(raw)
    return Document(blocks=tuple(_block(block) for block in stored.blocks))


def _block_json(block: Block) -> _HeadingJson | _ParagraphJson | _ListItemJson:
    match block:
        case Heading():
            return _HeadingJson(level=block.level, text=block.text)
        case Paragraph():
            return _ParagraphJson(mode=block.mode, lines=_lines_json(block.lines))
        case ListItem():
            return _ListItemJson(
                ordered=block.ordered, depth=block.depth, lines=_lines_json(block.lines)
            )


def _block(stored: _HeadingJson | _ParagraphJson | _ListItemJson) -> Block:
    match stored:
        case _HeadingJson():
            return Heading(level=stored.level, text=stored.text)
        case _ParagraphJson():
            return Paragraph(lines=_lines(stored.lines), mode=stored.mode)
        case _ListItemJson():
            return ListItem(lines=_lines(stored.lines), ordered=stored.ordered, depth=stored.depth)


def _lines_json(lines: tuple[Line, ...]) -> list[_LineJson]:
    return [
        _LineJson(text=line.text, start_ms=line.start_ms, end_ms=line.end_ms) for line in lines
    ]


def _lines(stored: list[_LineJson]) -> tuple[Line, ...]:
    return tuple(
        Line(text=line.text, start_ms=line.start_ms, end_ms=line.end_ms) for line in stored
    )
