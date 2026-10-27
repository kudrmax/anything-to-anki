"""The card layout is stored as JSON in one setting. Elements added to the app after the
layout was saved come hidden with their default style; elements the app no longer has
are dropped."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, Field, ValidationError

from backend.application.dto.card_layout_dtos import BlockStyleDTO, CardLayoutDTO
from backend.domain.exceptions import CardLayoutEditError
from backend.domain.ports.card_layout_repository import CardLayoutRepository
from backend.domain.value_objects.card_layout import (
    DEFAULT_CARD_LAYOUT,
    BlockRow,
    CardColumn,
    CardElement,
    CardLayout,
    ColumnWidth,
    DividerRow,
)

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.value_objects.card_layout import BlockStyle, CardRow

logger = logging.getLogger(__name__)

CARD_LAYOUT_SETTING = "card_layout"
_KNOWN_ELEMENTS: frozenset[str] = frozenset(CardElement)


class _StoredBlocks(BaseModel):
    kind: Literal["blocks"]
    elements: list[str]


class _StoredDivider(BaseModel):
    kind: Literal["divider"]


class _StoredColumn(BaseModel):
    width: ColumnWidth
    rows: list[Annotated[_StoredBlocks | _StoredDivider, Field(discriminator="kind")]]


class _StoredStyle(BaseModel):
    element: str
    style: BlockStyleDTO


class _StoredLayout(BaseModel):
    columns: list[_StoredColumn]
    styles: list[_StoredStyle]

    def to_domain(self) -> CardLayout:
        styles: dict[CardElement, BlockStyle] = dict(DEFAULT_CARD_LAYOUT.styles)
        for entry in self.styles:
            if entry.element in _KNOWN_ELEMENTS:
                styles[CardElement(entry.element)] = entry.style.to_domain()
        return CardLayout(
            columns=tuple(
                CardColumn(width=column.width, rows=self._rows(column)) for column in self.columns
            ),
            styles=styles,
        )

    @staticmethod
    def _rows(column: _StoredColumn) -> tuple[CardRow, ...]:
        rows: list[CardRow] = []
        for row in column.rows:
            if isinstance(row, _StoredDivider):
                rows.append(DividerRow())
                continue
            known = tuple(CardElement(e) for e in row.elements if e in _KNOWN_ELEMENTS)
            if known:
                rows.append(BlockRow(known))
        return tuple(rows)


class SettingsCardLayoutRepository(CardLayoutRepository):
    """CardLayoutRepository on top of the settings."""

    def __init__(self, settings: SettingsRepository) -> None:
        self._settings = settings

    def get(self) -> CardLayout:
        stored = self._settings.get(CARD_LAYOUT_SETTING)
        if stored is None:
            return DEFAULT_CARD_LAYOUT
        try:
            return _StoredLayout.model_validate_json(stored).to_domain()
        except (ValidationError, CardLayoutEditError):
            logger.exception("Stored card layout is unreadable, showing the default one")
            return DEFAULT_CARD_LAYOUT

    def save(self, layout: CardLayout) -> None:
        self._settings.set(CARD_LAYOUT_SETTING, CardLayoutDTO.of(layout).model_dump_json())
