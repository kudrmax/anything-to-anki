"""A change on an open review answers what changed and where the focus goes (spec §7), on
the app's real use cases: a press moves the focus on when its card became done, within its
section; cards a Rebuild brings join after their nearest held card with their fresh
section; an example takes the old card's place and the focus; an added word takes the
focus; a card that goes hands the focus to the card under it. A press on a frequent lemma
sends whole only the cards the review served."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.dto.review_dtos import OpenReviewRequest, ReviewContext
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import Press
from backend.domain.value_objects.rebuild_mode import RebuildMode
from backend.domain.value_objects.review_order import CardRow
from backend.domain.value_objects.source_scope import SourceScope
from backend.infrastructure.persistence.database import Base
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from tests.document_support import put_document
from tests.integration import test_card_state_projection_differential as corpus
from tests.integration.conftest import insert_source
from tests.projection_support import rebuild_projection
from tests.word_support import insert_word, phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from backend.application.dto.review_dtos import ReviewUpdateDTO
    from backend.application.utils.open_review import OpenReview
    from backend.infrastructure.container import Container

pytestmark = pytest.mark.integration

SCOPE = SourceScope.collection(corpus.COLLECTION).token
READY = CandidateSection.READY
# Source 1 of the corpus: a line that brings words no card has yet, and its last line,
# whose cards go when the line does.
NEW_LINE = "A weary albatross would hover above the frothy breakers."
LAST_LINE = len(corpus.SOURCES[1]) - 1
ADDED_LINE, ADDED_WORD = 1, 3


@pytest.fixture(scope="module")
def built() -> Iterator[corpus._Scenario]:  # noqa: SLF001
    """The differential test's corpus, processed once: each test gets a copy."""
    with corpus.processed_corpus() as processed:
        yield processed


class World:
    """One copy of the corpus with the collection's review open on it."""

    def __init__(self, scenario: corpus._Scenario) -> None:  # noqa: SLF001
        self.factory = scenario.fresh()
        self.container: Container = scenario.container

    def open(
        self, *, current: int | None = None, open_sections: list[CandidateSection] | None = None,
    ) -> ReviewUpdateDTO:
        with self.factory() as session:
            return self.container.open_review_use_case(session).execute(OpenReviewRequest(
                scope=SCOPE, requested_id=current,
                open_sections=list(CandidateSection) if open_sections is None else open_sections,
            ))

    def held(self, review_id: str) -> OpenReview:
        with self.container._review_order_store.hold(review_id) as review:  # noqa: SLF001
            return review

    def done(self, phrase_ids: list[int]) -> dict[int, bool]:
        with self.factory() as session:
            return self.container._card_state_query(session).done_of_phrases(phrase_ids)  # noqa: SLF001

    def press(self, ctx: ReviewContext, phrase_id: int, button: Press) -> ReviewUpdateDTO:
        with self.factory() as session:
            decide = self.container.decide_phrase_use_case(session)
            return self.container.review_mutation(session).press(
                ctx, phrase_id, lambda: decide.decide(phrase_id, button),
            )

    def changes(self, ctx: ReviewContext) -> ReviewUpdateDTO:
        with self.factory() as session:
            return self.container.review_window_use_case(session).changes(ctx)

    def write(self, change: Callable[[Session], object]) -> None:
        self.container.session_work().write(change)

    def card_ids(self, sql: str, **params: object) -> list[int]:
        with self.factory() as session:
            return list(session.scalars(text(sql), params))

    def source_one(self, *lines: str) -> None:
        """Source 1's text becomes `lines` and the source is rebuilt."""
        with self.factory() as session:
            put_document(session, 1, corpus.corpus_document(lines))
            session.commit()
        with self.factory() as session:
            self.container.rebuild_source_use_case(session).execute(1, RebuildMode.UPDATE)


@pytest.fixture()
def world(built: corpus._Scenario) -> World:  # noqa: SLF001
    return World(built)


def _ctx(update: ReviewUpdateDTO, current: int | None) -> ReviewContext:
    return ReviewContext(review_id=update.review_id, since=update.revision, current=current)


def _first_open_ready(world: World, review: OpenReview) -> int:
    ready = [review.order.phrase_id_at(i) for i in review.order.in_section(READY)]
    done = world.done(ready)
    return next(p for p in ready if not done[p])


# --- the focus after a press ----------------------------------------------------------------

def test_known_on_an_open_card_moves_the_focus_to_the_next_open_card_of_its_section(
    world: World,
) -> None:
    opened = world.open()
    review = world.held(opened.review_id)
    pressed = _first_open_ready(world, review)

    update = world.press(_ctx(opened, pressed), pressed, Press.KNOWN)

    ready = [review.order.phrase_id_at(i) for i in review.order.in_section(READY)]
    done = world.done(ready)
    after = ready[ready.index(pressed) + 1:] + ready[:ready.index(pressed)]
    assert update.focus_id == next(p for p in after if not done[p])
    assert update.done[pressed] is True
    assert update.layout is None


def test_undo_keeps_the_focus(world: World) -> None:
    opened = world.open()
    pressed = _first_open_ready(world, world.held(opened.review_id))
    first = world.press(_ctx(opened, pressed), pressed, Press.KNOWN)

    undone = world.press(_ctx(first, pressed), pressed, Press.KNOWN)

    assert undone.focus_id is None
    assert undone.done[pressed] is False


def test_another_button_on_a_done_card_keeps_the_focus(world: World) -> None:
    opened = world.open()
    pressed = _first_open_ready(world, world.held(opened.review_id))
    first = world.press(_ctx(opened, pressed), pressed, Press.LEARN)

    switched = world.press(_ctx(first, pressed), pressed, Press.CLOZE)

    assert switched.focus_id is None
    assert [c.choice for c in switched.cards if c.phrase_id == pressed] == ["cloze"]


def test_a_press_sends_fresh_the_served_cards_of_its_lemma_in_other_sources(
    world: World,
) -> None:
    broods = world.card_ids(
        "SELECT p.id FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
        " WHERE c.lemma = 'brood' AND c.source_id IN (1, 2) AND p.shown_by IS NOT NULL"
        " ORDER BY p.id",
    )
    assert len(broods) == 2
    pressed, other = broods
    opened = world.open()
    assert other in world.held(opened.review_id).served

    update = world.press(_ctx(opened, pressed), pressed, Press.LEARN)

    sent = {card.phrase_id: card for card in update.cards}
    assert sent[other].is_done is True
    assert update.done[other] is True


# --- cards that come and go ---------------------------------------------------------------

def test_cards_a_rebuild_brings_join_after_their_nearest_held_card_with_their_section(
    world: World,
) -> None:
    opened = world.open()
    before = list(world.held(opened.review_id).order.phrase_ids)

    world.source_one(*corpus.SOURCES[1], NEW_LINE)
    update = world.changes(_ctx(opened, None))

    review = world.held(opened.review_id)
    held = list(review.order.phrase_ids)
    new = [p for p in held if p not in before]
    assert new
    assert [p for p in held if p in before] == before
    assert update.layout is not None and update.layout.replace
    fresh = world.open()
    fresh_review = world.held(fresh.review_id)
    fresh_order = list(fresh_review.order.phrase_ids)
    for phrase_id in new:
        at = fresh_order.index(phrase_id)
        anchor = next((p for p in reversed(fresh_order[:at]) if p in before), None)
        between = held[held.index(anchor) + 1:held.index(phrase_id)] if anchor else (
            held[:held.index(phrase_id)]
        )
        assert all(p in new for p in between), phrase_id
        assert review.order.card(phrase_id) == fresh_review.order.card(phrase_id)


def test_a_card_that_goes_hands_the_focus_to_the_card_under_it(world: World) -> None:
    gone = world.card_ids(
        "SELECT p.id FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
        " WHERE c.source_id = 1 AND p.shown_by IS NOT NULL AND p.phrase_position LIKE :line"
        " ORDER BY p.id", line=f"[{LAST_LINE}, 0,%",
    )
    assert gone
    current = gone[0]
    opened = world.open(current=current)
    before = world.held(opened.review_id).layout()
    rows = [row.phrase_id for row in before.rows if isinstance(row, CardRow)]
    at = rows.index(current)
    expected = next(
        (p for p in rows[at + 1:] if p not in gone),
        next((p for p in reversed(rows[:at]) if p not in gone), None),
    )

    world.source_one(*corpus.SOURCES[1][:LAST_LINE])
    update = world.changes(_ctx(opened, current))

    assert set(gone) <= set(update.removed)
    assert update.focus_id == expected
    assert world.held(opened.review_id).order.card(current) is None


def test_an_example_takes_the_place_and_the_focus_of_the_card_it_replaces(
    world: World,
) -> None:
    [old] = world.card_ids(
        "SELECT p.id FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
        " WHERE c.lemma = 'brood' AND c.source_id = 1 AND p.shown_by IS NOT NULL",
    )
    opened = world.open(current=old)
    index = world.held(opened.review_id).order.index_of(old)

    with world.factory() as session:
        replace = world.container.replace_with_example_use_case(session)
        update = world.container.review_mutation(session).replace(
            _ctx(opened, old), old, lambda: replace.execute(old, corpus.SOURCES[2][0]),
        )

    order = world.held(opened.review_id).order
    assert update.focus_id is not None and update.focus_id != old
    assert order.index_of(update.focus_id) == index
    assert order.card(old) is None
    assert old in update.removed


def test_an_added_word_takes_the_focus(world: World) -> None:
    opened = world.open()
    selection = corpus._Projection._line(1, ADDED_LINE)  # noqa: SLF001

    with world.factory() as session:
        add = world.container.add_manual_candidate_use_case(session)
        update = world.container.review_mutation(session).add(
            _ctx(opened, None), lambda: add.execute(1, [ADDED_WORD], selection),
        )

    assert update.focus_id is not None
    assert world.held(opened.review_id).order.card(update.focus_id) is not None
    assert update.focus_id in {card.phrase_id for card in update.cards}


# --- a frequent lemma -----------------------------------------------------------------------

FREQUENT = "glare"
SOURCES, WORDS_PER_SOURCE = (1, 2, 3, 4, 5, 6), 40
# Each source's word `glare`, at its place in the source, each as frequent as given: the
# rarer ones stand among the Ready cards the review serves, the most frequent ones under a
# folded section.
FREQUENT_PLACE = 20
FREQUENT_ZIPF = {1: 2.6, 2: 3.0, 3: 3.4, 4: 5.6, 5: 6.0, 6: 6.4}


@pytest.fixture()
def book() -> Iterator[tuple[sessionmaker[Session], Container]]:
    """Six sources of 40 cards in a collection, one of each source's words `glare`."""
    from backend.infrastructure.api.dependencies import get_container

    engine = corpus._memory_engine()  # noqa: SLF001
    Base.metadata.create_all(engine)
    made = sessionmaker(bind=engine)
    with made() as session:
        session.execute(text(
            "INSERT INTO collections (id, name, position, created_at)"
            " VALUES (7, 'Book', 0, '2026-01-01 00:00:00')"
        ))
        for source_id in SOURCES:
            insert_source(session, source_id)
            session.execute(text("UPDATE sources SET collection_id = 7 WHERE id = :s"), {
                "s": source_id,
            })
            first = (source_id - 1) * WORDS_PER_SOURCE + 1
            for word_id in range(first, first + WORDS_PER_SOURCE):
                frequent = word_id - first == FREQUENT_PLACE
                insert_word(
                    session, word_id, source_id=source_id,
                    lemma=FREQUENT if frequent else None,
                    zipf_frequency=FREQUENT_ZIPF[source_id] if frequent else 3.0,
                )
        session.commit()
        rebuild_projection(session)
    yield made, get_container()
    engine.dispose()


def test_a_press_on_a_frequent_lemma_sends_whole_only_the_served_cards(
    book: tuple[sessionmaker[Session], Container],
) -> None:
    made, container = book
    with made() as session:
        opened = container.open_review_use_case(session).execute(OpenReviewRequest(scope="7"))
    with container._review_order_store.hold(opened.review_id) as review:  # noqa: SLF001
        served = set(review.served)
    frequent = [
        phrase_id_of((source_id - 1) * WORDS_PER_SOURCE + 1 + FREQUENT_PLACE)
        for source_id in SOURCES
    ]
    assert served & set(frequent)
    assert set(frequent) - served
    pressed = next(p for p in frequent if p in served)

    with made() as session:
        decide = container.decide_phrase_use_case(session)
        update = container.review_mutation(session).press(
            _ctx(opened, pressed), pressed, lambda: decide.decide(pressed, Press.KNOWN),
        )

    assert {card.phrase_id for card in update.cards} <= served
    assert served & set(frequent) <= {card.phrase_id for card in update.cards}
    assert {p for p, done in update.done.items() if done} >= set(frequent)
