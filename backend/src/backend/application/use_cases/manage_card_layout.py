from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from backend.application.dto.card_layout_dtos import (
    AddColumnEdit,
    CardLayoutViewDTO,
    HideBlockEdit,
    InsertDividerEdit,
    MoveBlockEdit,
    MoveRowEdit,
    RemoveColumnEdit,
    RemoveDividerEdit,
    ResetLayoutEdit,
    ResizeColumnEdit,
    RestyleBlockEdit,
)
from backend.domain.value_objects.card_layout import DEFAULT_CARD_LAYOUT, BlockPlace

if TYPE_CHECKING:
    from backend.application.dto.card_layout_dtos import CardLayoutEdit
    from backend.domain.ports.card_layout_repository import CardLayoutRepository
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.card_layout import CardLayout


class ManageCardLayoutUseCase:
    """Shows the card layout and applies the user's edits to it, one at a time."""

    def __init__(self, layouts: CardLayoutRepository, unit_of_work: UnitOfWork) -> None:
        self._layouts = layouts
        self._unit_of_work = unit_of_work

    def get(self) -> CardLayoutViewDTO:
        with self._unit_of_work.read():
            return CardLayoutViewDTO.of(self._layouts.get())

    def edit(self, edit: CardLayoutEdit) -> CardLayoutViewDTO:
        with self._unit_of_work.write():
            layout = self._edited(self._layouts.get(), edit)
            self._layouts.save(layout)
        return CardLayoutViewDTO.of(layout)

    @staticmethod
    def _edited(layout: CardLayout, edit: CardLayoutEdit) -> CardLayout:
        match edit:
            case MoveBlockEdit():
                place = BlockPlace(column=edit.column, row=edit.row, position=edit.position)
                return layout.move_block(edit.element, place)
            case HideBlockEdit():
                return layout.hide_block(edit.element)
            case RestyleBlockEdit():
                changes = {
                    name: value
                    for name in ("size", "tone", "bold", "align")
                    if (value := getattr(edit, name)) is not None
                }
                style = replace(layout.styles[edit.element], **changes)
                return layout.restyle(edit.element, style)
            case InsertDividerEdit():
                return layout.insert_divider(edit.column, edit.row)
            case RemoveDividerEdit():
                return layout.remove_divider(edit.column, edit.row)
            case MoveRowEdit():
                to = BlockPlace(edit.to_column, edit.to_row)
                return layout.move_row(edit.column, edit.row, to)
            case AddColumnEdit():
                return layout.add_column()
            case RemoveColumnEdit():
                return layout.remove_column(edit.column)
            case ResizeColumnEdit():
                return layout.resize_column(edit.column, edit.width)
            case ResetLayoutEdit():
                return DEFAULT_CARD_LAYOUT
