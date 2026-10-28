from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

from backend.domain.exceptions import CardLayoutEditError

if TYPE_CHECKING:
    from collections.abc import Mapping


class CardElement(StrEnum):
    """A part of the card body the user places. The phrase above and the decisions and
    tools below are not elements: they stay where they are."""

    TARGET = "target"
    TRANSLATION = "translation"
    # The second line of the meaning: it retells the phrase's context.
    CONTEXT = "context"
    DEFINITION = "definition"
    # Whatever the meaning says after the definition and the context.
    NOTES = "notes"
    SYNONYMS = "synonyms"
    EXAMPLES = "examples"
    TRANSCRIPTION = "transcription"
    PRONUNCIATION = "pronunciation"
    TTS = "tts"
    WORD_FACTS = "word_facts"
    VIDEO_FRAME = "video_frame"
    PICTURE = "picture"
    # What the card offers while it has no meaning yet: its progress, Generate or Retry.
    MEANING_STATUS = "meaning_status"


class ElementKind(StrEnum):
    """What a style can change in an element: text takes size, tone and weight, media
    takes size, a control keeps its own look."""

    TEXT = "text"
    MEDIA = "media"
    CONTROL = "control"


class BlockSize(StrEnum):
    XS = "xs"
    S = "s"
    M = "m"
    L = "l"
    XL = "xl"


class BlockTone(StrEnum):
    ACCENT = "accent"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    MUTED = "muted"


class BlockAlign(StrEnum):
    """Where a block stands in its row: from the start, or pushed to the end."""

    START = "start"
    END = "end"


class BlockVAlign(StrEnum):
    """Where a block stands in its row's height: on the row's text line, top, middle or bottom."""

    BASELINE = "baseline"
    TOP = "top"
    MIDDLE = "middle"
    BOTTOM = "bottom"


class BlockSpace(StrEnum):
    """Extra room on one side of a block, on top of the usual gap between blocks."""

    NONE = "none"
    S = "s"
    M = "m"
    L = "l"


class ColumnWidth(StrEnum):
    NARROW = "narrow"
    NORMAL = "normal"
    WIDE = "wide"


ELEMENT_KIND: Mapping[CardElement, ElementKind] = {
    CardElement.TARGET: ElementKind.TEXT,
    CardElement.TRANSLATION: ElementKind.TEXT,
    CardElement.CONTEXT: ElementKind.TEXT,
    CardElement.DEFINITION: ElementKind.TEXT,
    CardElement.NOTES: ElementKind.TEXT,
    CardElement.SYNONYMS: ElementKind.TEXT,
    CardElement.EXAMPLES: ElementKind.TEXT,
    CardElement.TRANSCRIPTION: ElementKind.TEXT,
    CardElement.PRONUNCIATION: ElementKind.CONTROL,
    CardElement.TTS: ElementKind.CONTROL,
    CardElement.WORD_FACTS: ElementKind.TEXT,
    CardElement.VIDEO_FRAME: ElementKind.MEDIA,
    CardElement.PICTURE: ElementKind.MEDIA,
    CardElement.MEANING_STATUS: ElementKind.CONTROL,
}

MIN_COLUMNS = 1
MAX_COLUMNS = 3


@dataclass(frozen=True)
class BlockStyle:
    size: BlockSize = BlockSize.M
    tone: BlockTone = BlockTone.PRIMARY
    bold: bool = False
    align: BlockAlign = BlockAlign.START
    valign: BlockVAlign = BlockVAlign.BASELINE
    space_top: BlockSpace = BlockSpace.NONE
    space_right: BlockSpace = BlockSpace.NONE
    space_bottom: BlockSpace = BlockSpace.NONE
    space_left: BlockSpace = BlockSpace.NONE


@dataclass(frozen=True)
class BlockRow:
    """Elements side by side in one line, wrapping when the column is too narrow."""

    elements: tuple[CardElement, ...]


@dataclass(frozen=True)
class DividerRow:
    """A line across the column."""


type CardRow = BlockRow | DividerRow


@dataclass(frozen=True)
class CardColumn:
    width: ColumnWidth
    rows: tuple[CardRow, ...]


@dataclass(frozen=True)
class BlockPlace:
    """Where a block goes, counted on the layout before it moves: a new row of its own
    before row `row`, or — with `position` — into row `row` before its `position`-th block."""

    column: int
    row: int
    position: int | None = None


type _Rows = list[list[CardElement] | DividerRow]


@dataclass(frozen=True)
class CardLayout:
    """How the card body is laid out: columns of rows, every element placed at most once,
    and each element's style, kept while the element is hidden."""

    columns: tuple[CardColumn, ...]
    styles: Mapping[CardElement, BlockStyle]

    def __post_init__(self) -> None:
        if not MIN_COLUMNS <= len(self.columns) <= MAX_COLUMNS:
            raise CardLayoutEditError(f"A card has {MIN_COLUMNS} to {MAX_COLUMNS} columns")
        placed = self.placed
        if len(placed) != len(set(placed)):
            raise CardLayoutEditError("An element is placed twice")
        if any(isinstance(r, BlockRow) and not r.elements for c in self.columns for r in c.rows):
            raise CardLayoutEditError("A row of blocks is empty")
        if set(self.styles) != set(CardElement):
            raise CardLayoutEditError("Every element needs a style")

    @property
    def placed(self) -> list[CardElement]:
        return [
            element
            for column in self.columns
            for row in column.rows
            if isinstance(row, BlockRow)
            for element in row.elements
        ]

    @property
    def hidden(self) -> tuple[CardElement, ...]:
        placed = set(self.placed)
        return tuple(element for element in CardElement if element not in placed)

    @property
    def can_add_column(self) -> bool:
        return len(self.columns) < MAX_COLUMNS

    @property
    def can_remove_column(self) -> bool:
        return len(self.columns) > MIN_COLUMNS

    def move_block(self, element: CardElement, place: BlockPlace) -> CardLayout:
        """Puts the element at `place`; a hidden element is shown there."""
        columns = self._editable()
        rows = self._rows_at(columns, place.column)
        source = self._find(element)
        if place.position is None:
            self._check_gap(rows, place.row)
            rows.insert(place.row, [element])
            if source and source[0] == place.column and place.row <= source[1]:
                source = (source[0], source[1] + 1, source[2])
        else:
            target = self._block_row(rows, place.row)
            if not 0 <= place.position <= len(target):
                raise CardLayoutEditError(f"No position {place.position} in row {place.row}")
            target.insert(place.position, element)
            if source and source[:2] == (place.column, place.row) and place.position <= source[2]:
                source = (source[0], source[1], source[2] + 1)
        if source:
            self._remove(columns, *source)
        return self._built(columns)

    def hide_block(self, element: CardElement) -> CardLayout:
        source = self._find(element)
        if source is None:
            return self
        columns = self._editable()
        self._remove(columns, *source)
        return self._built(columns)

    def restyle(self, element: CardElement, style: BlockStyle) -> CardLayout:
        return replace(self, styles={**self.styles, element: style})

    def insert_divider(self, column: int, row: int) -> CardLayout:
        columns = self._editable()
        rows = self._rows_at(columns, column)
        self._check_gap(rows, row)
        rows.insert(row, DividerRow())
        return self._built(columns)

    def remove_divider(self, column: int, row: int) -> CardLayout:
        columns = self._editable()
        rows = self._rows_at(columns, column)
        if not 0 <= row < len(rows) or not isinstance(rows[row], DividerRow):
            raise CardLayoutEditError(f"Row {row} of column {column} is not a divider")
        del rows[row]
        return self._built(columns)

    def move_row(self, column: int, row: int, to: BlockPlace) -> CardLayout:
        """Moves a whole row, a divider included, before row `to.row` of column `to.column`."""
        columns = self._editable()
        rows = self._rows_at(columns, column)
        target = self._rows_at(columns, to.column)
        if not 0 <= row < len(rows):
            raise CardLayoutEditError(f"No row {row} in column {column}")
        self._check_gap(target, to.row)
        moved = rows.pop(row)
        target.insert(to.row - 1 if to.column == column and to.row > row else to.row, moved)
        return self._built(columns)

    def add_column(self) -> CardLayout:
        column = CardColumn(width=ColumnWidth.NORMAL, rows=())
        return replace(self, columns=(*self.columns, column))

    def remove_column(self, column: int) -> CardLayout:
        """Removes a column; its rows go to the end of the column before it, or to the
        start of the next one when it is the first."""
        self._column(column)
        if not self.can_remove_column:
            raise CardLayoutEditError("The card keeps at least one column")
        removed = self.columns[column]
        columns = list(self.columns)
        del columns[column]
        if column == 0:
            neighbour = columns[0]
            columns[0] = replace(neighbour, rows=(*removed.rows, *neighbour.rows))
        else:
            neighbour = columns[column - 1]
            columns[column - 1] = replace(neighbour, rows=(*neighbour.rows, *removed.rows))
        return replace(self, columns=tuple(columns))

    def resize_column(self, column: int, width: ColumnWidth) -> CardLayout:
        self._column(column)
        columns = list(self.columns)
        columns[column] = replace(columns[column], width=width)
        return replace(self, columns=tuple(columns))

    def _column(self, column: int) -> CardColumn:
        if not 0 <= column < len(self.columns):
            raise CardLayoutEditError(f"No column {column}")
        return self.columns[column]

    def _find(self, element: CardElement) -> tuple[int, int, int] | None:
        for c, column in enumerate(self.columns):
            for r, row in enumerate(column.rows):
                if isinstance(row, BlockRow) and element in row.elements:
                    return c, r, row.elements.index(element)
        return None

    def _editable(self) -> list[_Rows]:
        return [
            [list(row.elements) if isinstance(row, BlockRow) else row for row in column.rows]
            for column in self.columns
        ]

    def _rows_at(self, columns: list[_Rows], column: int) -> _Rows:
        self._column(column)
        return columns[column]

    @staticmethod
    def _check_gap(rows: _Rows, row: int) -> None:
        if not 0 <= row <= len(rows):
            raise CardLayoutEditError(f"No place before row {row}")

    @staticmethod
    def _block_row(rows: _Rows, row: int) -> list[CardElement]:
        found = rows[row] if 0 <= row < len(rows) else None
        if not isinstance(found, list):
            raise CardLayoutEditError(f"Row {row} is not a row of blocks")
        return found

    @staticmethod
    def _remove(columns: list[_Rows], column: int, row: int, position: int) -> None:
        elements = columns[column][row]
        assert isinstance(elements, list)
        del elements[position]
        if not elements:
            del columns[column][row]

    def _built(self, columns: list[_Rows]) -> CardLayout:
        return replace(
            self,
            columns=tuple(
                replace(
                    column,
                    rows=tuple(
                        BlockRow(tuple(row)) if isinstance(row, list) else row for row in rows
                    ),
                )
                for column, rows in zip(self.columns, columns, strict=True)
            ),
        )


# The card as it was before it could be laid out: what you decide by on the left, the
# reference on the right.
DEFAULT_CARD_LAYOUT = CardLayout(
    columns=(
        CardColumn(
            width=ColumnWidth.NORMAL,
            rows=(
                BlockRow((CardElement.TARGET,)),
                DividerRow(),
                BlockRow((CardElement.TRANSLATION,)),
                BlockRow((CardElement.CONTEXT,)),
                BlockRow((CardElement.MEANING_STATUS,)),
                BlockRow((CardElement.VIDEO_FRAME, CardElement.PICTURE)),
            ),
        ),
        CardColumn(
            width=ColumnWidth.NORMAL,
            rows=(
                BlockRow(
                    (
                        CardElement.TRANSCRIPTION,
                        CardElement.PRONUNCIATION,
                        CardElement.TTS,
                        CardElement.WORD_FACTS,
                    ),
                ),
                BlockRow((CardElement.SYNONYMS,)),
                BlockRow((CardElement.DEFINITION,)),
                BlockRow((CardElement.NOTES,)),
                BlockRow((CardElement.EXAMPLES,)),
            ),
        ),
    ),
    styles={
        CardElement.TARGET: BlockStyle(BlockSize.XL, BlockTone.ACCENT, bold=True),
        CardElement.TRANSLATION: BlockStyle(BlockSize.XL, BlockTone.PRIMARY, bold=True),
        CardElement.CONTEXT: BlockStyle(BlockSize.L, BlockTone.PRIMARY),
        CardElement.DEFINITION: BlockStyle(BlockSize.M, BlockTone.SECONDARY),
        CardElement.NOTES: BlockStyle(BlockSize.M, BlockTone.MUTED),
        CardElement.SYNONYMS: BlockStyle(BlockSize.M, BlockTone.MUTED),
        CardElement.EXAMPLES: BlockStyle(BlockSize.M, BlockTone.MUTED),
        CardElement.TRANSCRIPTION: BlockStyle(BlockSize.S, BlockTone.MUTED),
        CardElement.PRONUNCIATION: BlockStyle(),
        CardElement.TTS: BlockStyle(),
        CardElement.WORD_FACTS: BlockStyle(BlockSize.S, BlockTone.MUTED, align=BlockAlign.END),
        CardElement.VIDEO_FRAME: BlockStyle(),
        CardElement.PICTURE: BlockStyle(),
        CardElement.MEANING_STATUS: BlockStyle(),
    },
)
