from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.collection import Collection
from backend.domain.exceptions import (
    CollectionMoveNotAllowedError,
    CollectionNameExistsError,
    CollectionNotFoundError,
)
from backend.domain.services.collection_tree import MAX_DEPTH, CollectionTree

SHOWS = Collection(id=1, name="Shows", position=0)
FRIENDS = Collection(id=2, name="Friends", parent_id=1, position=0)
SEASON_1 = Collection(id=3, name="Season 1", parent_id=2, position=0)
PILOT = Collection(id=4, name="Pilot", parent_id=3, position=0)
SEASON_2 = Collection(id=5, name="Season 2", parent_id=2, position=1)
EXTRAS = Collection(id=9, name="Extras", parent_id=5, position=0)
IELTS = Collection(id=6, name="IELTS", position=1)
WORM = Collection(id=7, name="Worm", position=2)
GONE = Collection(id=8, name="Gone", position=3, deleted_at=datetime(2026, 1, 1, tzinfo=UTC))

# Shows(1) ─ Friends(2) ┬ Season 1(3) ─ Pilot(4)
#                       └ Season 2(5) ─ Extras(9)
# IELTS(6)
# Worm(7)


def tree() -> CollectionTree:
    return CollectionTree([WORM, SEASON_2, PILOT, FRIENDS, GONE, IELTS, EXTRAS, SEASON_1, SHOWS])


@pytest.mark.unit
class TestLookup:
    def test_children_in_manual_order_without_deleted(self) -> None:
        assert [c.name for c in tree().children(None)] == ["Shows", "IELTS", "Worm"]
        assert [c.name for c in tree().children(2)] == ["Season 1", "Season 2"]

    def test_deleted_collection_is_not_found(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            tree().get(8)

    def test_next_position_follows_last_sibling(self) -> None:
        assert tree().next_position(None) == 3
        assert tree().next_position(6) == 0

    def test_find_top_level_ignores_case_and_subcollections(self) -> None:
        assert tree().find_top_level("worm") == WORM
        assert tree().find_top_level("Season 1") is None

    def test_index_of(self) -> None:
        assert tree().index_of(5) == 1


@pytest.mark.unit
class TestShape:
    def test_depth(self) -> None:
        assert [tree().depth(i) for i in (1, 2, 3, 4, 6)] == [1, 2, 3, 4, 1]

    def test_height(self) -> None:
        assert [tree().height(i) for i in (1, 2, 3, 4, 6)] == [4, 3, 2, 1, 1]

    def test_ancestors_root_first(self) -> None:
        assert [c.id for c in tree().ancestors(4)] == [1, 2, 3]
        assert tree().ancestors(1) == []

    def test_path_at_any_depth(self) -> None:
        assert tree().path(4) == ["Shows", "Friends", "Season 1", "Pilot"]
        assert tree().path(6) == ["IELTS"]

    def test_subtree_spans_all_levels(self) -> None:
        assert tree().subtree_ids(1) == {1, 2, 3, 4, 5, 9}
        assert tree().descendant_ids(2) == {3, 4, 5, 9}
        assert tree().subtree_ids(4) == {4}

    def test_cycle_in_data_does_not_hang(self) -> None:
        looped = CollectionTree([
            Collection(id=1, name="A", parent_id=2), Collection(id=2, name="B", parent_id=1),
        ])
        assert looped.subtree_ids(1) == {1, 2}
        assert len(looped.ancestors(1)) <= 2
        assert looped.height(1) >= 1


@pytest.mark.unit
class TestNames:
    def test_check_name_trims(self) -> None:
        assert tree().check_name("  Lost ", None) == "Lost"

    def test_check_name_rejects_case_insensitive_duplicate_among_siblings(self) -> None:
        with pytest.raises(CollectionNameExistsError):
            tree().check_name(" season 1", 2)

    def test_check_name_allows_same_name_under_another_parent(self) -> None:
        assert tree().check_name("Season 1", 6) == "Season 1"

    def test_check_name_allows_keeping_own_name(self) -> None:
        assert tree().check_name("SEASON 1", 2, exclude_id=3) == "SEASON 1"

    def test_check_name_ignores_deleted_siblings(self) -> None:
        assert tree().check_name("Gone", None) == "Gone"

    @pytest.mark.parametrize("name", ["", "   ", "x" * 201])
    def test_check_name_rejects_empty_and_long(self, name: str) -> None:
        with pytest.raises(ValueError):
            tree().check_name(name, None)


@pytest.mark.unit
class TestDepthLimit:
    def test_default_limit_is_five(self) -> None:
        assert MAX_DEPTH == 5

    def test_child_may_be_created_at_depth_five(self) -> None:
        tree().check_parent(4)
        assert tree().can_hold_children(4)

    def test_child_at_depth_six_is_rejected(self) -> None:
        fifth = Collection(id=10, name="Cold open", parent_id=4)
        deep = CollectionTree([SHOWS, FRIENDS, SEASON_1, PILOT, fifth])
        assert not deep.can_hold_children(10)
        with pytest.raises(CollectionMoveNotAllowedError, match="deeper than 5 levels"):
            deep.check_parent(10)

    def test_top_level_needs_no_parent(self) -> None:
        tree().check_parent(None)

    def test_unknown_parent_is_not_found(self) -> None:
        with pytest.raises(CollectionNotFoundError):
            tree().check_parent(99)

    def test_limit_is_a_parameter(self) -> None:
        small = CollectionTree([SHOWS, FRIENDS, SEASON_1, IELTS], max_depth=3)
        small.check_parent(2)
        assert not small.can_hold_children(3)
        with pytest.raises(CollectionMoveNotAllowedError, match="deeper than 3 levels"):
            small.check_parent(3)
        with pytest.raises(CollectionMoveNotAllowedError, match="deeper than 3 levels"):
            small.place(6, 3, 0)
        assert small.move_targets(6) == [None, 1, 2]


@pytest.mark.unit
class TestPlace:
    def test_reorder_among_siblings(self) -> None:
        changed = tree().place(7, None, 0)
        assert {(c.id, c.position) for c in changed} == {(7, 0), (1, 1), (6, 2)}

    def test_leaf_goes_inside(self) -> None:
        changed = tree().place(7, 6, 0)
        moved = next(c for c in changed if c.id == 7)
        assert (moved.parent_id, moved.position) == (6, 0)

    def test_subcollection_goes_to_top_level_and_closes_gap(self) -> None:
        changed = {c.id: c for c in tree().place(3, None, 1)}
        assert (changed[3].parent_id, changed[3].position) == (None, 1)
        assert changed[5].position == 0  # Season 2 moves up in Friends
        assert changed[6].position == 2

    def test_collection_with_children_may_be_nested(self) -> None:
        changed = {c.id: c for c in tree().place(2, 6, 0)}
        assert changed[2].parent_id == 6

    def test_two_level_subtree_fits_under_depth_three(self) -> None:
        changed = {c.id: c for c in tree().place(3, 5, 0)}  # 3 + 2 = 5
        assert changed[3].parent_id == 5

    def test_two_level_subtree_does_not_fit_under_depth_four(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError, match="deeper than 5 levels"):
            tree().place(3, 9, 0)  # 4 + 2 = 6

    def test_position_is_clamped(self) -> None:
        changed = {c.id: c for c in tree().place(1, None, 99)}
        assert changed[1].position == 2

    def test_cannot_go_inside_itself(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError):
            tree().place(6, 6, 0)

    def test_cannot_go_inside_own_descendant(self) -> None:
        with pytest.raises(CollectionMoveNotAllowedError, match="own subcollection"):
            tree().place(2, 4, 0)

    def test_name_must_be_free_in_new_parent(self) -> None:
        clash = Collection(id=10, name="season 1", position=4)
        with pytest.raises(CollectionNameExistsError):
            CollectionTree([SHOWS, FRIENDS, SEASON_1, clash]).place(10, 2, 0)


@pytest.mark.unit
class TestMoveTargets:
    def test_leaf_may_go_anywhere_else(self) -> None:
        assert tree().move_targets(7) == [None, 1, 2, 3, 4, 5, 9, 6]

    def test_deep_subtree_avoids_itself_and_depths_it_would_overflow(self) -> None:
        assert tree().move_targets(2) == [None, 1, 6, 7]
        assert tree().move_targets(3) == [None, 1, 2, 5, 6, 7]

    def test_current_parent_is_a_target(self) -> None:
        assert 2 in tree().move_targets(5)
