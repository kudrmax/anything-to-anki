"""`POST /phrases/{id}/decision {button}` through the press table (design §2.4): every row
answers with the card as it is after the press and the press that undoes it; a refused press
is 409 and changes nothing."""
from __future__ import annotations

from collections.abc import Callable, Generator  # noqa: TC003
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from backend.application.utils.knowledge_scope import KnowledgeScope
from backend.domain.entities.occurrence import Occurrence
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.learning_timer import LEARNING_KNOWN_AFTER
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy
from backend.infrastructure.api.app import app
from backend.infrastructure.api.dependencies import get_db_session, get_session_factory
from backend.infrastructure.container import KNOWLEDGE_SCOPE_KEY
from backend.infrastructure.persistence.database import Base, _enable_sqlite_foreign_keys
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_learning_query import SqlaLearningQuery
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from backend.infrastructure.persistence.sqla_word_mark_repository import (
    SqlaWordMarkRepository,
)
from fastapi.testclient import TestClient
from httpx import Response  # noqa: TC002
from sqlalchemy import StaticPool, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from tests.decision_support import NOW, FixedClock
from tests.integration.conftest import insert_source
from tests.phrase_support import phrase
from tests.projection_support import rebuild_projection
from tests.review_support import card_in, on_review
from tests.review_window_support import review_list
from tests.word_marks_support import insert_known
from tests.word_support import bind, insert_word, phrase_id_of

pytestmark = pytest.mark.integration

# JSON of the API, read as the web reads it.
Json = Any

WORD, OTHER_WORD = 1, 50
HERE, THERE = 1, 2
CARD = phrase_id_of(WORD)
SIBLING = 5000
LEMMA = "glare"
FRESH = (NOW - timedelta(days=1)).replace(tzinfo=None).isoformat(sep=" ")
DUE = (NOW - LEARNING_KNOWN_AFTER).replace(tzinfo=None).isoformat(sep=" ")


class Seed:
    """The word glare of source 1 with its card CARD and a sibling card SIBLING."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def choice(self, phrase_id: int, choice: str) -> Seed:
        self.session.execute(
            text("UPDATE phrases SET choice = :c WHERE id = :id"), {"c": choice, "id": phrase_id},
        )
        return self

    def in_anki(self, choice: str, *, since: str = FRESH, kind: str = "learn") -> Seed:
        self.choice(CARD, choice)
        bind(self.session, WORD, CARD, lemma=LEMMA, kind=kind, since=since)
        return self

    def listed_known(self) -> Seed:
        insert_known(self.session, "glare", "NOUN")
        return self

    def known_in_another_source(self) -> Seed:
        insert_word(self.session, OTHER_WORD, source_id=THERE, lemma=LEMMA, status="known")
        return self.listed_known()


@dataclass(frozen=True)
class Row:
    """A press-table row: the card's state, the press, and the card it leaves."""

    given: Callable[[Seed], object]
    phrase_id: int
    button: str
    choice: str
    status: str
    in_anki: bool = False
    released: bool = False


def _open(seed: Seed) -> None:
    del seed


ROWS: dict[str, Row] = {
    "P1 open: learn": Row(_open, CARD, "learn", "learn", "learn"),
    "P1 skipped: learn": Row(lambda s: s.choice(CARD, "skip"), CARD, "learn", "learn", "learn"),
    "P2 open: cloze": Row(_open, CARD, "cloze", "cloze", "learn"),
    "P3 open: known": Row(_open, CARD, "known", "known", "known"),
    "P3 skipped: known": Row(lambda s: s.choice(CARD, "skip"), CARD, "known", "known", "known"),
    "P4 open: skip": Row(_open, CARD, "skip", "skip", "new"),
    "P5 skipped: skip": Row(lambda s: s.choice(CARD, "skip"), CARD, "skip", "none", "new"),
    "P9 learn: learn": Row(lambda s: s.choice(CARD, "learn"), CARD, "learn", "none", "new"),
    "P9 cloze: cloze": Row(lambda s: s.choice(CARD, "cloze"), CARD, "cloze", "none", "new"),
    "P10 learn: cloze": Row(lambda s: s.choice(CARD, "learn"), CARD, "cloze", "cloze", "learn"),
    "P10 cloze: learn": Row(lambda s: s.choice(CARD, "cloze"), CARD, "learn", "learn", "learn"),
    "P11 learn: known": Row(lambda s: s.choice(CARD, "learn"), CARD, "known", "known", "known"),
    "P12 learn: skip": Row(lambda s: s.choice(CARD, "learn"), CARD, "skip", "skip", "new"),
    "P13 known: known": Row(
        lambda s: s.choice(CARD, "known").listed_known(), CARD, "known", "none", "new",
    ),
    "P14 known: learn": Row(
        lambda s: s.choice(CARD, "known").listed_known(), CARD, "learn", "learn", "learn",
    ),
    "P15 known: skip": Row(
        lambda s: s.choice(CARD, "known").listed_known(), CARD, "skip", "skip", "new",
    ),
    "P16 in Anki, learn: known": Row(
        lambda s: s.in_anki("learn"), CARD, "known", "known", "known", in_anki=True,
    ),
    "P17 in Anki, learn: learn": Row(
        lambda s: s.in_anki("learn"), CARD, "learn", "none", "new", released=True,
    ),
    "P17 in Anki, cloze: cloze": Row(
        lambda s: s.in_anki("cloze", kind="cloze"), CARD, "cloze", "none", "new",
        released=True,
    ),
    "P18 in Anki, learn: cloze": Row(
        lambda s: s.in_anki("learn"), CARD, "cloze", "cloze", "learn", released=True,
    ),
    "P19 in Anki, learn: skip": Row(
        lambda s: s.in_anki("learn"), CARD, "skip", "skip", "new", released=True,
    ),
    "P20 in Anki, known: known": Row(
        lambda s: s.in_anki("known").listed_known(), CARD, "known", "none", "new",
        released=True,
    ),
    "P21 in Anki, known: skip": Row(
        lambda s: s.in_anki("known").listed_known(), CARD, "skip", "skip", "new",
        released=True,
    ),
    "P22 in Anki, known: learn": Row(
        lambda s: s.in_anki("known").listed_known(), CARD, "learn", "learn", "learn",
        released=True,
    ),
    "P23 in Anki, known by its timer: known": Row(
        lambda s: s.in_anki("learn", since=DUE), CARD, "known", "none", "new", released=True,
    ),
    "P24 in Anki, known by its timer: learn": Row(
        lambda s: s.in_anki("learn", since=DUE), CARD, "learn", "learn", "learn",
        released=True,
    ),
    "P24s in Anki, known by its timer: skip": Row(
        lambda s: s.in_anki("learn", since=DUE), CARD, "skip", "skip", "new", released=True,
    ),
}

REFUSALS: dict[str, tuple[Callable[[Seed], object], int, str, str, str]] = {
    # given, phrase, button, refusal, detail
    "P6 decided elsewhere: learn": (
        lambda s: s.known_in_another_source(), CARD, "learn", "decided_elsewhere",
        "Already known",
    ),
    "P6 decided elsewhere: cloze": (
        lambda s: s.known_in_another_source(), CARD, "cloze", "decided_elsewhere",
        "Already known",
    ),
    "P6 decided elsewhere: known": (
        lambda s: s.known_in_another_source(), CARD, "known", "decided_elsewhere",
        "Already known",
    ),
    "P6 decided elsewhere: skip": (
        lambda s: s.known_in_another_source(), CARD, "skip", "decided_elsewhere",
        "Already known",
    ),
    "P6 decided elsewhere, skipped: skip": (
        lambda s: s.known_in_another_source().choice(CARD, "skip"), CARD, "skip",
        "decided_elsewhere", "Already known",
    ),
    "P25 sibling of a learn: learn": (
        lambda s: s.choice(CARD, "learn"), SIBLING, "learn", "not_decision_card",
        "Learned via another phrase: change it on that card",
    ),
    "P25 sibling of a learn: cloze": (
        lambda s: s.choice(CARD, "learn"), SIBLING, "cloze", "not_decision_card",
        "Learned via another phrase: change it on that card",
    ),
    "P25 sibling of a known: known": (
        lambda s: s.choice(CARD, "known").listed_known(), SIBLING, "known",
        "not_decision_card", "Known via another phrase: change it on that card",
    ),
    "P25 sibling of a known: skip": (
        lambda s: s.choice(CARD, "known").listed_known(), SIBLING, "skip",
        "not_decision_card", "Known via another phrase: change it on that card",
    ),
    "P27 skipped sibling of a learn: skip": (
        lambda s: s.choice(SIBLING, "skip").choice(CARD, "learn"), SIBLING, "skip",
        "not_decision_card", "Learned via another phrase: change it on that card",
    ),
    "P27 skipped sibling of a learn: learn": (
        lambda s: s.choice(SIBLING, "skip").choice(CARD, "learn"), SIBLING, "learn",
        "not_decision_card", "Learned via another phrase: change it on that card",
    ),
}


@pytest.fixture()
def factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        insert_source(session, HERE)
        insert_source(session, THERE)
        insert_word(session, WORD, lemma=LEMMA, phrase_text="He glared at me.")
        sibling = SqlaOccurrenceRepository(session, SessionChangeRecorder(session)).add(Occurrence(
            candidate_id=WORD, origin=OccurrenceOrigin.MANUAL,
            source_phrase=phrase("She glared back.", "glared"), phrase_position=None,
            key=None, fragment_score=None,
            earned_section=CandidateSection.READY, shown_by=ShownBy.USER,
        ))
        session.execute(
            text("UPDATE phrases SET id = :id WHERE id = :old"),
            {"id": SIBLING, "old": sibling.id},
        )
        session.commit()
        _rebuild_at_now(session)
    yield sessionmaker(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            _at_now(session)
            yield session

    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _given(factory: sessionmaker[Session], given: Callable[[Seed], object]) -> None:
    with factory() as session:
        given(Seed(session))
        session.commit()
        _rebuild_at_now(session)


def _at_now(session: Session) -> None:
    """The session reads what the user knows at NOW."""
    session.info[KNOWLEDGE_SCOPE_KEY] = KnowledgeScope(
        clock=FixedClock(NOW),
        word_mark_repo=SqlaWordMarkRepository(session, SessionChangeRecorder(session)),
        learning_query=SqlaLearningQuery(session),
    )


def _rebuild_at_now(session: Session) -> None:
    """The review list reads the projection: rows seeded straight into the tables reach it
    by a rebuild at NOW, as the app's start makes one."""
    _at_now(session)
    rebuild_projection(session)


def _bindings(factory: sessionmaker[Session]) -> tuple[int, int]:
    """(active, released) bindings of CARD."""
    with factory() as session:
        active, released = session.execute(text(
            "SELECT sum(released_at IS NULL), sum(released_at IS NOT NULL)"
            " FROM anki_synced_cards WHERE phrase_id = :id"
        ), {"id": CARD}).one()
    return int(active or 0), int(released or 0)


def _decide(client: TestClient, phrase_id: int, button: str) -> Response:
    return on_review(
        client, "POST", f"/phrases/{phrase_id}/decision", json={"button": button},
        current=phrase_id,
    )


def _undo(client: TestClient, phrase_id: int, button: str) -> Response:
    return on_review(
        client, "POST", f"/phrases/{phrase_id}/decision/undo", json={"button": button},
        current=phrase_id,
    )


def _card(client: TestClient, phrase_id: int) -> Json:
    cards = review_list(client, f"source-{HERE}")
    return next(card for card in cards if card["phrase_id"] == phrase_id)


@pytest.mark.parametrize("name", ROWS)
def test_each_press_answers_with_the_card_it_leaves(
    client: TestClient, factory: sessionmaker[Session], name: str,
) -> None:
    row = ROWS[name]
    _given(factory, row.given)

    response = _decide(client, row.phrase_id, row.button)

    assert response.status_code == 200, response.text
    card = card_in(response.json(), row.phrase_id)
    assert (card["choice"], card["shown"]["status"]) == (row.choice, row.status)
    assert card == _card(client, row.phrase_id) | {"section": card["section"]}
    assert _bindings(factory) == (int(row.in_anki), int(row.released))


@pytest.mark.parametrize("name", ROWS)
def test_the_undo_a_press_offers_brings_the_card_back_and_focuses_it(
    client: TestClient, factory: sessionmaker[Session], name: str,
) -> None:
    row = ROWS[name]
    _given(factory, row.given)
    before = _card(client, row.phrase_id)["choice"]
    undo = _decide(client, row.phrase_id, row.button).json()["undo"]
    if before == row.choice:
        assert undo is None, "a press that keeps the choice has no press to undo it"
        return
    assert undo["phrase_id"] == row.phrase_id

    response = _undo(client, row.phrase_id, undo["button"])

    assert response.status_code == 200, response.text
    assert card_in(response.json(), row.phrase_id)["choice"] == before
    assert response.json()["focus_id"] == row.phrase_id
    assert response.json()["undo"] is None


def test_a_refused_undo_is_409_and_changes_nothing(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    undo = _decide(client, CARD, "learn").json()["undo"]
    _given(factory, lambda s: s.choice(CARD, "none").known_in_another_source())
    before = _card(client, CARD)

    response = _undo(client, CARD, undo["button"])

    assert (response.status_code, response.json()["detail"]) == (409, "Already known")
    assert _card(client, CARD) == before


@pytest.mark.parametrize("name", REFUSALS)
def test_a_refused_press_is_409_and_changes_nothing(
    client: TestClient, factory: sessionmaker[Session], name: str,
) -> None:
    given, phrase_id, button, refusal, detail = REFUSALS[name]
    _given(factory, given)
    before = _card(client, phrase_id)
    shown = next(b for b in before["state"]["buttons"] if b["button"] == button)
    assert (shown["command"], shown["refused"]) == (None, refusal)

    response = _decide(client, phrase_id, button)

    assert (response.status_code, response.json()["detail"]) == (409, detail)
    assert _card(client, phrase_id) == before


def test_the_card_tells_what_each_button_does(client: TestClient) -> None:
    card = _card(client, CARD)

    assert card["choice"] == "none"
    assert card["shown"] == {
        "status": "new", "skipped": False, "where": "nowhere", "tone": "open",
    }
    assert card["can_edit_cloze"] is False
    assert card["state"]["buttons"] == [
        {"button": "learn", "command": "decide", "pressed": False, "refused": None,
         "closes": "lemma"},
        {"button": "cloze", "command": "edit_cloze", "pressed": False, "refused": None,
         "closes": "lemma"},
        {"button": "known", "command": "decide", "pressed": False, "refused": None,
         "closes": "lemma"},
        {"button": "skip", "command": "decide", "pressed": False, "refused": None,
         "closes": "card"},
    ]
    for gone in ("status", "word_status", "phrase_skipped", "is_decision", "decision_kind",
                 "can_cloze"):
        assert gone not in card
    assert set(card["state"]) == {"buttons"}


def test_on_a_cloze_card_cloze_undoes_and_its_markup_is_editable(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    _given(factory, lambda s: s.choice(CARD, "cloze"))

    card = _card(client, CARD)

    cloze = next(b for b in card["state"]["buttons"] if b["button"] == "cloze")
    assert (cloze["command"], cloze["pressed"]) == ("decide", True)
    assert card["can_edit_cloze"] is True


def test_a_cloze_in_anki_keeps_its_markup(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    _given(factory, lambda s: s.in_anki("cloze", kind="cloze"))

    card = _card(client, CARD)

    assert card["can_edit_cloze"] is False
    assert card["shown"]["status"] == "learning"
    assert [b["button"] for b in card["state"]["buttons"] if b["pressed"]] == ["cloze"]


def test_a_card_known_by_its_timer_shows_known_pressed(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    _given(factory, lambda s: s.in_anki("learn", since=DUE))

    card = _card(client, CARD)

    assert card["shown"]["status"] == "known"
    assert [b["button"] for b in card["state"]["buttons"] if b["pressed"]] == ["known"]


def test_learn_cloze_known_skip_and_none_on_one_card(client: TestClient) -> None:
    for button, choice in (
        ("learn", "learn"), ("cloze", "cloze"), ("known", "known"), ("skip", "skip"),
        ("skip", "none"),
    ):
        assert card_in(_decide(client, CARD, button).json(), CARD)["choice"] == choice


def test_an_unknown_phrase_is_404(client: TestClient) -> None:
    assert _decide(client, 999, "learn").status_code == 404


def test_an_unknown_button_is_422(client: TestClient) -> None:
    assert _decide(client, CARD, "pending").status_code == 422


def test_the_old_decision_api_is_gone(client: TestClient) -> None:
    response = client.put(f"/phrases/{CARD}/decision", json={"status": "learn"})

    assert response.status_code == 405


def test_removing_known_frees_the_word_kept_by_a_deleted_sources_known_card(
    client: TestClient, factory: sessionmaker[Session],
) -> None:
    """PRINCIPLE: a Known card in Anki of a deleted source leaves an orphaned binding;
    removing Known in Settings makes the word NEW, not Learning until that binding's timer."""
    _given(factory, lambda s: s.in_anki("learn"))
    assert _decide(client, CARD, "known").status_code == 200
    _given(factory, lambda s: insert_word(s.session, OTHER_WORD, source_id=THERE, lemma=LEMMA))
    assert client.delete(f"/sources/{HERE}").status_code == 204

    listed = next(w for w in client.get("/known-words").json() if w["lemma"] == LEMMA)
    assert client.delete(f"/known-words/{listed['removal_key']}").status_code == 200

    assert client.get("/vocabulary/learning").json()["in_anki"] == []
    other = next(
        card
        for card in review_list(client, f"source-{THERE}")
        if card["phrase_id"] == phrase_id_of(OTHER_WORD)
    )
    assert other["shown"]["status"] == "new"
    assert all(b["refused"] is None for b in other["state"]["buttons"])
    with factory() as session:
        active = session.execute(text(
            "SELECT count(*) FROM anki_synced_cards WHERE lemma = :l AND released_at IS NULL"
        ), {"l": LEMMA}).scalar_one()
    assert active == 0, "no binding is left to bring Known back by its timer"
