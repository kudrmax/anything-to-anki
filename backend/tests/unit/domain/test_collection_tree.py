from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import (
    CollectionMoveNotAllowedError,
    CollectionNameExistsError,
    CollectionNotFoundError,
)
from backend.domain.services.collection_tree import CollectionTree

FRIENDS = Collection(id=1, name="Friends", position=0)
SEASON_1 = Collection(id=2, name="Season 1", parent_id=1, position=0)
SEASON_2 = Collection(id=3, name="Season 2", parent_id=1, position=1)
IELTS = Collection(id=4, name="IELTS", position=1)
WORM = Collection(id=5, name="Worm", position=2)
GONE = Collection(id=6, name="Gone", position=3, deleted_at=datetime(2026, 1, 1, tzinfo=UTC))


def tree() -> CollectionTree:
    return CollectionTree([WORM, SEASON_2, FRIENDS, GONE, IELTS, SEASON_1])


@pytest.mark.unit
class TestLookup:
    def test_children_in_manual_order_without_deleted(self) -> None:
        assert [c.name for c in tree().children(None)] == ["Friends", "IELTS", "Worm"]
        assert [c.name for c in tree().children(1)] == ["Season 1", "Season 2"]

    def test_deleted_collection_is_not_found(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            tree().get(6)

    def test_subtree_of_collection_holds_its_subcollections(self) -> None:
        assert tree().subtree_ids(1) == {1, 2, 3}
        assert tree().subtree_ids(2) == {2}

    def test_path(self) -> None:
        assert tree().path(2) == ["Friends", "Season 1"]
        assert tree().path(4) == ["IELTS"]

    def test_next_position_follows_last_sibling(self) -> None:
        assert tree().next_position(None) == 3
        assert tree().next_position(4) == 0

    def test_find_top_level_ignores_case_and_subcollections(self) -> None:
        assert tree().find_top_level("worm") == WORM
        assert tree().find_top_level("Season 1") is None


@pytest.mark.unit
class TestNames:
    def test_check_name_trims(self) -> None:
        assert tree().check_name("  Lost ", None) == "Lost"

    def test_check_name_rejects_case_insensitive_duplicate_among_siblings(self) -> None:
        with pytest.raises(CollectionNameExistsError):
            tree().check_name(" season 1", 1)

    def test_check_name_allows_same_name_under_another_parent(self) -> None:
        assert tree().check_name("Season 1", 4) == "Season 1"

    def test_check_name_allows_keeping_own_name(self) -> None:
        assert tree().check_name("SEASON 1", 1, exclude_id=2) == "SEASON 1"

    def test_check_name_ignores_deleted_siblings(self) -> None:
        assert tree().check_name("Gone", None) == "Gone"

    @pytest.mark.parametrize("name", ["", "   ", "x" * 201])
    def test_check_name_rejects_empty_and_long(self, name: str) -> None:
        with pytest.raises(ValueError):
            tree().check_name(name, None)

    def test_subcollection_cannot_be_parent(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError):
            tree().check_parent(2)


@pytest.mark.unit
class TestPlace:
    def test_reorder_among_siblings(self) -> None:
        changed = tree().place(5, None, 0)
        assert {(c.id, c.position) for c in changed} == {(5, 0), (1, 1), (4, 2)}

    def test_collection_without_children_goes_inside(self) -> None:
        changed = tree().place(5, 4, 0)
        moved = next(c for c in changed if c.id == 5)
        assert (moved.parent_id, moved.position) == (4, 0)

    def test_subcollection_goes_to_top_level_and_closes_gap(self) -> None:
        changed = {c.id: c for c in tree().place(2, None, 1)}
        assert (changed[2].parent_id, changed[2].position) == (None, 1)
        assert changed[3].position == 0  # Season 2 moves up in Friends
        assert changed[4].position == 2

    def test_position_is_clamped(self) -> None:
        changed = {c.id: c for c in tree().place(1, None, 99)}
        assert changed[1].position == 2

    def test_cannot_go_inside_itself(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError):
            tree().place(4, 4, 0)

    def test_collection_with_subcollections_stays_top_level(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError):
            tree().place(1, 4, 0)

    def test_cannot_go_inside_subcollection(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError):
            tree().place(5, 2, 0)

    def test_name_must_be_free_in_new_parent(self) -> None:
        clash = Collection(id=7, name="season 1", position=4)
        with pytest.raises(CollectionNameExistsError):
            CollectionTree([FRIENDS, SEASON_1, clash]).place(7, 1, 0)

    def test_index_of(self) -> None:
        assert tree().index_of(3) == 1
