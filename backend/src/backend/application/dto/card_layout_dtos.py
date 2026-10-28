from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from backend.domain.value_objects.card_layout import (
    ALWAYS_SHOWN,
    ELEMENT_KIND,
    BlockAlign,
    BlockRow,
    BlockSize,
    BlockSpace,
    BlockStyle,
    BlockTone,
    BlockVAlign,
    CardColumn,
    CardElement,
    CardLayout,
    ColumnWidth,
    DividerRow,
    ElementKind,
)


class BlockStyleDTO(BaseModel):
    size: BlockSize
    tone: BlockTone
    bold: bool
    align: BlockAlign
    # Layouts saved before these settings existed get the defaults.
    valign: BlockVAlign = BlockVAlign.BASELINE
    space_top: BlockSpace = BlockSpace.NONE
    space_right: BlockSpace = BlockSpace.NONE
    space_bottom: BlockSpace = BlockSpace.NONE
    space_left: BlockSpace = BlockSpace.NONE

    @classmethod
    def of(cls, style: BlockStyle) -> BlockStyleDTO:
        return cls.model_validate(asdict(style))

    def to_domain(self) -> BlockStyle:
        return BlockStyle(**self.model_dump())


class BlockRowDTO(BaseModel):
    kind: Literal["blocks"] = "blocks"
    elements: list[CardElement]


class DividerRowDTO(BaseModel):
    kind: Literal["divider"] = "divider"


CardRowDTO = Annotated[BlockRowDTO | DividerRowDTO, Field(discriminator="kind")]


class CardColumnDTO(BaseModel):
    width: ColumnWidth
    rows: list[CardRowDTO]


class ElementStyleDTO(BaseModel):
    element: CardElement
    style: BlockStyleDTO


class CardLayoutDTO(BaseModel):
    """The layout as it is stored and sent: columns of rows and every element's style."""

    columns: list[CardColumnDTO]
    styles: list[ElementStyleDTO]

    @classmethod
    def of(cls, layout: CardLayout) -> CardLayoutDTO:
        return cls(
            columns=[
                CardColumnDTO(
                    width=column.width,
                    rows=[
                        BlockRowDTO(elements=list(row.elements))
                        if isinstance(row, BlockRow)
                        else DividerRowDTO()
                        for row in column.rows
                    ],
                )
                for column in layout.columns
            ],
            styles=[
                ElementStyleDTO(element=element, style=BlockStyleDTO.of(layout.styles[element]))
                for element in CardElement
            ],
        )

    def to_domain(self) -> CardLayout:
        return CardLayout(
            columns=tuple(
                CardColumn(
                    width=column.width,
                    rows=tuple(
                        BlockRow(tuple(row.elements))
                        if isinstance(row, BlockRowDTO)
                        else DividerRow()
                        for row in column.rows
                    ),
                )
                for column in self.columns
            ),
            styles={entry.element: entry.style.to_domain() for entry in self.styles},
        )


class CardElementDTO(BaseModel):
    """An element the layout places, and what its style can change."""

    element: CardElement
    kind: ElementKind
    # False — the block is always on the card: Review shows it by its own switch.
    can_hide: bool


class CardLayoutViewDTO(BaseModel):
    """The layout to show and edit."""

    layout: CardLayoutDTO
    elements: list[CardElementDTO]
    hidden: list[CardElement]
    can_add_column: bool
    can_remove_column: bool

    @classmethod
    def of(cls, layout: CardLayout) -> CardLayoutViewDTO:
        return cls(
            layout=CardLayoutDTO.of(layout),
            elements=[
                CardElementDTO(element=e, kind=ELEMENT_KIND[e], can_hide=e not in ALWAYS_SHOWN)
                for e in CardElement
            ],
            hidden=list(layout.hidden),
            can_add_column=layout.can_add_column,
            can_remove_column=layout.can_remove_column,
        )


class MoveBlockEdit(BaseModel):
    """Puts a block, a hidden one included, into a new row before `row`, or — with
    `position` — into row `row` before its `position`-th block. Places count on the
    layout before the move."""

    kind: Literal["move_block"] = "move_block"
    element: CardElement
    column: int
    row: int
    position: int | None = None


class HideBlockEdit(BaseModel):
    kind: Literal["hide_block"] = "hide_block"
    element: CardElement


class RestyleBlockEdit(BaseModel):
    """Changes the given parts of a block's style."""

    kind: Literal["restyle_block"] = "restyle_block"
    element: CardElement
    size: BlockSize | None = None
    tone: BlockTone | None = None
    bold: bool | None = None
    align: BlockAlign | None = None
    valign: BlockVAlign | None = None
    space_top: BlockSpace | None = None
    space_right: BlockSpace | None = None
    space_bottom: BlockSpace | None = None
    space_left: BlockSpace | None = None


class InsertDividerEdit(BaseModel):
    kind: Literal["insert_divider"] = "insert_divider"
    column: int
    row: int


class RemoveDividerEdit(BaseModel):
    kind: Literal["remove_divider"] = "remove_divider"
    column: int
    row: int


class MoveRowEdit(BaseModel):
    """Moves a whole row before row `to_row` of column `to_column`, counted before the move."""

    kind: Literal["move_row"] = "move_row"
    column: int
    row: int
    to_column: int
    to_row: int


class AddColumnEdit(BaseModel):
    kind: Literal["add_column"] = "add_column"


class RemoveColumnEdit(BaseModel):
    kind: Literal["remove_column"] = "remove_column"
    column: int


class ResizeColumnEdit(BaseModel):
    kind: Literal["resize_column"] = "resize_column"
    column: int
    width: ColumnWidth


class ResetLayoutEdit(BaseModel):
    kind: Literal["reset"] = "reset"


CardLayoutEdit = Annotated[
    MoveBlockEdit
    | HideBlockEdit
    | RestyleBlockEdit
    | InsertDividerEdit
    | RemoveDividerEdit
    | MoveRowEdit
    | AddColumnEdit
    | RemoveColumnEdit
    | ResizeColumnEdit
    | ResetLayoutEdit,
    Field(discriminator="kind"),
]
