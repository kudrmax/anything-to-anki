from __future__ import annotations

import pytest
from backend.domain.exceptions import CardLayoutEditError
from backend.domain.value_objects.card_layout import (
    DEFAULT_CARD_LAYOUT,
    MAX_COLUMNS,
    BlockPlace,
    BlockRow,
    BlockSize,
    BlockStyle,
    CardColumn,
    CardElement,
    CardLayout,
    CardRow,
    ColumnWidth,
    DividerRow,
)

E = CardElement


def layout(*columns: tuple[CardRow, ...]) -> CardLayout:
    return CardLayout(
        columns=tuple(CardColumn(ColumnWidth.NORMAL, rows) for rows in columns),
        styles=DEFAULT_CARD_LAYOUT.styles,
    )


def rows(card: CardLayout, column: int = 0) -> tuple[CardRow, ...]:
    return card.columns[column].rows


def blocks(*elements: CardElement) -> BlockRow:
    return BlockRow(elements)


class TestDefault:
    def test_places_every_element(self) -> None:
        assert DEFAULT_CARD_LAYOUT.hidden == ()

    def test_separates_target_from_translation(self) -> None:
        assert rows(DEFAULT_CARD_LAYOUT)[:3] == (
            blocks(E.TARGET), DividerRow(), blocks(E.TRANSLATION),
        )


class TestInvariants:
    def test_element_placed_once(self) -> None:
        with pytest.raises(CardLayoutEditError):
            layout((blocks(E.TARGET), blocks(E.TARGET)))

    def test_no_empty_block_row(self) -> None:
        with pytest.raises(CardLayoutEditError):
            layout((blocks(),))

    def test_column_count(self) -> None:
        with pytest.raises(CardLayoutEditError):
            layout()
        with pytest.raises(CardLayoutEditError):
            layout(*[()] * (MAX_COLUMNS + 1))

    def test_unplaced_elements_are_hidden(self) -> None:
        card = layout((blocks(E.TARGET),))
        assert E.TARGET not in card.hidden
        assert E.TRANSLATION in card.hidden


class TestMoveBlock:
    def test_into_new_row(self) -> None:
        card = layout((blocks(E.TARGET), blocks(E.TRANSLATION)))
        moved = card.move_block(E.TRANSLATION, BlockPlace(0, 0))
        assert rows(moved) == (blocks(E.TRANSLATION), blocks(E.TARGET))

    def test_down_counts_places_before_the_move(self) -> None:
        card = layout((blocks(E.TARGET), blocks(E.TRANSLATION), blocks(E.CONTEXT)))
        moved = card.move_block(E.TARGET, BlockPlace(0, 2))
        assert rows(moved) == (blocks(E.TRANSLATION), blocks(E.TARGET), blocks(E.CONTEXT))

    def test_joins_a_row(self) -> None:
        card = layout((blocks(E.TRANSCRIPTION), blocks(E.PRONUNCIATION)))
        moved = card.move_block(E.PRONUNCIATION, BlockPlace(0, 0, position=1))
        assert rows(moved) == (blocks(E.TRANSCRIPTION, E.PRONUNCIATION),)

    def test_reorders_within_a_row(self) -> None:
        card = layout((blocks(E.TRANSCRIPTION, E.PRONUNCIATION, E.TTS),))
        moved = card.move_block(E.TRANSCRIPTION, BlockPlace(0, 0, position=3))
        assert rows(moved) == (blocks(E.PRONUNCIATION, E.TTS, E.TRANSCRIPTION),)
        moved = card.move_block(E.TTS, BlockPlace(0, 0, position=0))
        assert rows(moved) == (blocks(E.TTS, E.TRANSCRIPTION, E.PRONUNCIATION),)

    def test_onto_itself_changes_nothing(self) -> None:
        card = layout((blocks(E.TARGET),))
        assert card.move_block(E.TARGET, BlockPlace(0, 0, position=0)) == card
        assert card.move_block(E.TARGET, BlockPlace(0, 1)) == card

    def test_out_of_a_row_into_its_own(self) -> None:
        card = layout((blocks(E.TRANSCRIPTION, E.TTS),))
        moved = card.move_block(E.TTS, BlockPlace(0, 1))
        assert rows(moved) == (blocks(E.TRANSCRIPTION), blocks(E.TTS))

    def test_to_another_column(self) -> None:
        card = layout((blocks(E.TARGET), blocks(E.SYNONYMS)), (blocks(E.DEFINITION),))
        moved = card.move_block(E.SYNONYMS, BlockPlace(1, 0))
        assert rows(moved, 0) == (blocks(E.TARGET),)
        assert rows(moved, 1) == (blocks(E.SYNONYMS), blocks(E.DEFINITION))

    def test_shows_a_hidden_element(self) -> None:
        card = layout((blocks(E.TARGET),))
        moved = card.move_block(E.PICTURE, BlockPlace(0, 1))
        assert rows(moved) == (blocks(E.TARGET), blocks(E.PICTURE))
        assert E.PICTURE not in moved.hidden

    def test_cannot_join_a_divider(self) -> None:
        card = layout((DividerRow(),))
        with pytest.raises(CardLayoutEditError):
            card.move_block(E.TARGET, BlockPlace(0, 0, position=0))

    def test_place_outside(self) -> None:
        card = layout((blocks(E.TARGET),))
        with pytest.raises(CardLayoutEditError):
            card.move_block(E.TARGET, BlockPlace(0, 2))
        with pytest.raises(CardLayoutEditError):
            card.move_block(E.TARGET, BlockPlace(1, 0))


class TestHideAndStyle:
    def test_hide_drops_the_emptied_row(self) -> None:
        card = layout((blocks(E.TARGET), blocks(E.TRANSLATION)))
        assert rows(card.hide_block(E.TARGET)) == (blocks(E.TRANSLATION),)

    def test_style_survives_hiding(self) -> None:
        style = BlockStyle(size=BlockSize.XS)
        card = layout((blocks(E.TARGET),)).restyle(E.TARGET, style)
        shown = card.hide_block(E.TARGET).move_block(E.TARGET, BlockPlace(0, 0))
        assert shown.styles[E.TARGET] == style


class TestRows:
    def test_insert_and_remove_divider(self) -> None:
        card = layout((blocks(E.TARGET), blocks(E.TRANSLATION)))
        divided = card.insert_divider(0, 1)
        assert rows(divided) == (blocks(E.TARGET), DividerRow(), blocks(E.TRANSLATION))
        assert divided.remove_divider(0, 1) == card

    def test_remove_divider_only_removes_dividers(self) -> None:
        with pytest.raises(CardLayoutEditError):
            layout((blocks(E.TARGET),)).remove_divider(0, 0)

    def test_move_row_down(self) -> None:
        card = layout((DividerRow(), blocks(E.TARGET), blocks(E.TRANSLATION)))
        moved = card.move_row(0, 0, BlockPlace(0, 2))
        assert rows(moved) == (blocks(E.TARGET), DividerRow(), blocks(E.TRANSLATION))

    def test_move_row_to_another_column(self) -> None:
        card = layout((DividerRow(), blocks(E.TARGET)), ())
        moved = card.move_row(0, 0, BlockPlace(1, 0))
        assert rows(moved, 0) == (blocks(E.TARGET),)
        assert rows(moved, 1) == (DividerRow(),)


class TestColumns:
    def test_add_up_to_the_limit(self) -> None:
        card = layout(())
        for _ in range(MAX_COLUMNS - 1):
            card = card.add_column()
        assert not card.can_add_column
        with pytest.raises(CardLayoutEditError):
            card.add_column()

    def test_removed_column_rows_go_to_the_previous_one(self) -> None:
        card = layout((blocks(E.TARGET),), (blocks(E.DEFINITION),))
        merged = card.remove_column(1)
        assert rows(merged) == (blocks(E.TARGET), blocks(E.DEFINITION))

    def test_removed_first_column_rows_go_to_the_next_one(self) -> None:
        card = layout((blocks(E.TARGET),), (blocks(E.DEFINITION),))
        merged = card.remove_column(0)
        assert rows(merged) == (blocks(E.TARGET), blocks(E.DEFINITION))

    def test_keeps_one_column(self) -> None:
        card = layout((blocks(E.TARGET),))
        assert not card.can_remove_column
        with pytest.raises(CardLayoutEditError):
            card.remove_column(0)

    def test_resize(self) -> None:
        card = layout(()).resize_column(0, ColumnWidth.WIDE)
        assert card.columns[0].width is ColumnWidth.WIDE
