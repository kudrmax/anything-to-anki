from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.application.utils.review_answer import window_around
from backend.domain.services.review_layout import (
    focus_after_removal,
    remove_cards,
    replace_card,
)
from backend.domain.value_objects.review_order import HeldCard
from backend.domain.value_objects.source_scope import SourceScope

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from backend.application.dto.review_dtos import ReviewContext, ReviewUpdateDTO
    from backend.application.utils.open_review import OpenReview
    from backend.application.utils.review_answer import ReviewAnswer
    from backend.application.utils.review_ordering import ReviewOrdering
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.value_objects.card_state_rows import CardStateRow
    from backend.domain.value_objects.review_order import ReviewOrder

# How many cards of a section the focus after a press reads at a time: the next open card
# is nearly always among the first ones under the pressed card.
DONE_READ_AHEAD = 256

type FocusRule = Callable[[ReviewOrder, Mapping[int, bool]], int | None]
"""Where the focus goes, from the order with the changes placed and whether each card is
done now; None leaves it."""


@dataclass(frozen=True)
class Placement:
    """The card `new_id` takes the place of `old_id` in the held order."""

    old_id: int
    new_id: int


class ReviewUpdates:
    """What changed for an open review since the client's revision, placed into the held
    order: gone cards leave it, new ones join it by the domain rules, and the answer holds
    the changed cards the client was served, whether every changed card of the set is
    done, and the next focus. Called under the review's lock; reads one snapshot."""

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        card_states: CardStateQuery,
        ordering: ReviewOrdering,
        answer: ReviewAnswer,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._card_states = card_states
        self._ordering = ordering
        self._answer = answer
        self._unit_of_work = unit_of_work

    def build(
        self,
        ctx: ReviewContext,
        review: OpenReview,
        *,
        focus_id: int | None = None,
        focus_by: FocusRule | None = None,
        placement: Placement | None = None,
    ) -> ReviewUpdateDTO:
        """`focus_id`: the card the focus goes to, else where `focus_by` says; when neither
        says and the current card is gone, the card next to it in the list."""
        with self._unit_of_work.read():
            scope = SourceScope.parse(review.scope_token)
            source_ids = [
                s.id for s in self._scope_resolver.reviewable_sources(scope) if s.id is not None
            ]
            changed = self._card_states.changed_since(source_ids, ctx.since)
            live = {c.row.phrase_id: c.row for c in changed if not c.removed}
            removed = [c.row.phrase_id for c in changed if c.removed]
            # A source that left the set takes its cards out; one that joined brings all of
            # its live cards, whatever revision they were written at.
            held = review.source_ids
            current = frozenset(source_ids)
            for card in self._card_states.changed_since(sorted(held - current), 0):
                removed.append(card.row.phrase_id)
                live.pop(card.row.phrase_id, None)
            for card in self._card_states.changed_since(sorted(current - held), 0):
                if not card.removed:
                    live[card.row.phrase_id] = card.row
            if current != held:
                review.source_ids = current
                review.contents_version += 1
            version = review.layout_version
            review.current = ctx.current
            before = review.layout()
            gone = {p for p in removed if review.order.index_of(p) is not None}
            order = self._placed(review, source_ids, live, removed, placement)
            if order is not review.order:
                review.reorder(order)
            if focus_id is None and focus_by is not None:
                focus_id = focus_by(review.order, _StoredDone(
                    review.order, self._card_states, {p: r.is_done for p, r in live.items()},
                ))
            if focus_id is None and ctx.current in gone:
                focus_id = focus_after_removal(before, ctx.current, gone)
            if focus_id is not None:
                review.current = focus_id
            layout = review.layout()
            replace = review.layout_version != version
            window = None
            if not replace and focus_id is not None and focus_id not in review.served:
                window = window_around(layout, focus_id)
            return self._answer.of(
                ctx.review_id, review, window=window, replace=replace, focus_id=focus_id,
                changed=live.keys(), removed=removed,
                done={p: row.is_done for p, row in live.items()},
            )

    def _placed(
        self,
        review: OpenReview,
        source_ids: list[int],
        live: Mapping[int, CardStateRow],
        removed: list[int],
        placement: Placement | None,
    ) -> ReviewOrder:
        """The held order with the gone cards out and the new ones in: a replacing card in
        the place of the one it replaces, every other one after its nearest held card in the
        order the set has now. Each new card takes the section it has now."""
        order = review.order
        step = self._ordering.step()
        if placement is not None:
            new = live.get(placement.new_id)
            if (
                new is not None and order.index_of(new.phrase_id) is None
                and order.index_of(placement.old_id) is not None
            ):
                order = replace_card(
                    order, placement.old_id,
                    HeldCard(new.phrase_id, new.word_id, new.sections.at(step)),
                )
        order = remove_cards(order, removed)
        new_words = {p: row.word_id for p, row in live.items() if order.index_of(p) is None}
        if new_words:
            order = self._ordering.placed(order, source_ids, review.sort, step, new_words)
        return order


class _StoredDone(Mapping[int, bool]):
    """Whether each card of the order is done, as stored now: read from the projection a
    run of its section at a time, as the focus rule walks the order. A card the projection
    has no live row for counts as done: the focus never goes to it."""

    def __init__(
        self, order: ReviewOrder, card_states: CardStateQuery, known: dict[int, bool],
    ) -> None:
        self._order = order
        self._card_states = card_states
        self._known = known

    def __getitem__(self, phrase_id: int) -> bool:
        if phrase_id not in self._known:
            self._read_ahead(phrase_id)
        return self._known.get(phrase_id, True)

    def __iter__(self) -> Iterator[int]:
        return iter(self._order.phrase_ids)

    def __len__(self) -> int:
        return len(self._order)

    def _read_ahead(self, phrase_id: int) -> None:
        order = self._order
        index = order.index_of(phrase_id)
        if index is None:
            self._known[phrase_id] = True
            return
        if order.sectioned:
            run = order.in_section(order.section_at(index))
            start = order.rank_at(index)
        else:
            run, start = range(len(order)), index
        ids = [
            order.phrase_id_at(at) for at in run[start:start + DONE_READ_AHEAD]
        ]
        missing = [p for p in ids if p not in self._known]
        found = self._card_states.done_of_phrases(missing)
        self._known.update({p: found.get(p, True) for p in missing})
