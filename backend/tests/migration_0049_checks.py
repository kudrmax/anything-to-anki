"""The asserts of design §4.1 for migration 0049, over any database at revision 0048.

`read_before` reads the old cards before the upgrade; `check_upgraded` asserts every §4.1
row on the upgraded database and returns the counts to report. The expected outcome of
every card comes from an oracle written from the §4 mapping table, independent of the
migration's code. `app_export_queue` runs the app's own ExportQueue on the upgraded
database, for `check_upgraded` to compare with the oracle. Both the synthetic fixture test
and the prod-copy test run these.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from backend.application.utils.export_queue import ExportQueue
from backend.infrastructure.persistence.session_change_recorder import SessionChangeRecorder
from backend.infrastructure.persistence.sqla_candidate_repository import SqlaCandidateRepository
from backend.infrastructure.persistence.sqla_occurrence_repository import (
    SqlaOccurrenceRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.decision_support import Decisions, project_words

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Iterable
    from pathlib import Path

DECIDED = ("learn", "known")
DECISION_CHOICES = ("learn", "cloze", "known")
STATUSES = frozenset({"pending", "learn", "learning", "known"})
PHRASE_LEVEL_JOB_TYPES = ("polish", "meaning", "media", "tts")
ACTIVE_JOB_STATUSES = ("queued", "running")
TIMER_DAYS = 30
# Released export records, by why the migration released them.
KNOWN_REMOVED = "known removed after the export"
NOT_DECIDED = "pending or skip"
MERGE_LOSER = "merge loser"
# From this revision on, a binding holds its card's choice only once the card is gone.
CHOICE_ON_ORPHANS_ONLY = "0055"


@dataclass(frozen=True)
class OldCard:
    id: int
    source_id: int
    lemma: str
    pos: str
    is_phrasal_verb: bool
    status: str
    latest_synced_row: int
    has_cloze: bool
    source_phrase: str
    phrase_position: str | None

    @property
    def exported(self) -> bool:
        return self.latest_synced_row > 0

    @property
    def group(self) -> tuple[int, str, bool]:
        return (self.source_id, self.lemma.lower(), self.is_phrasal_verb)

    @property
    def rank(self) -> tuple[bool, int, bool, bool, int]:
        """§4: an exported card, the latest export, a decision (not skip), Known over
        Learn, the id."""
        return (
            self.exported, self.latest_synced_row, self.status in DECIDED,
            self.status == "known", self.id,
        )


@dataclass(frozen=True)
class OldRow:
    id: int
    card_id: int
    note_id: int


@dataclass(frozen=True)
class Before:
    cards: tuple[OldCard, ...]
    rows: tuple[OldRow, ...]
    known_words: frozenset[tuple[str, str | None]]
    unknown_words: frozenset[str]
    clozes: int
    calibration: frozenset[tuple[object, ...]]
    reports: int
    jobs: int
    phrase_jobs: int
    progress: dict[int, tuple[int, int]]

    @property
    def known(self) -> frozenset[str]:
        """Lemmas in Known, any POS, lowercase; Unknown wins."""
        return frozenset(lemma.lower() for lemma, _ in self.known_words) - self.unknown_words

    def winners(self) -> dict[tuple[int, str, bool], OldCard]:
        groups: dict[tuple[int, str, bool], list[OldCard]] = defaultdict(list)
        for card in self.cards:
            groups[card.group].append(card)
        return {key: max(group, key=lambda c: c.rank) for key, group in groups.items()}

    def decided_losers(self) -> list[int]:
        winners = self.winners()
        return sorted(
            c.id for c in self.cards if winners[c.group] is not c and c.status in DECIDED
        )


@dataclass
class Report:
    counts: Counter[str] = field(default_factory=Counter)
    listed: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    progress_after: dict[int, tuple[int, int]] = field(default_factory=dict)

    def list(self, reason: str, item: int) -> None:
        self.counts[reason] += 1
        self.listed[reason].append(item)


def read_before(conn: sqlite3.Connection) -> Before:
    latest = dict(conn.execute(
        "SELECT candidate_id, max(id) FROM anki_synced_cards GROUP BY candidate_id"
    ).fetchall())
    clozed = {row[0] for row in conn.execute("SELECT candidate_id FROM candidate_clozes")}
    cards = tuple(
        OldCard(
            id=row[0], source_id=row[1], lemma=row[2], pos=row[3],
            is_phrasal_verb=bool(row[4]), status=row[5],
            latest_synced_row=int(latest.get(row[0], 0)), has_cloze=row[0] in clozed,
            source_phrase=row[6], phrase_position=row[7],
        )
        for row in conn.execute(
            "SELECT id, source_id, lemma, pos, is_phrasal_verb, status, source_phrase,"
            " phrase_position FROM candidates ORDER BY id"
        )
    )
    progress: dict[int, tuple[int, int]] = {}
    for source_id, decided, total in conn.execute(
        "SELECT source_id, sum(status != 'pending'), count(*) FROM candidates GROUP BY source_id"
    ):
        progress[source_id] = (int(decided), int(total))
    return Before(
        cards=cards,
        rows=tuple(
            OldRow(*row) for row in conn.execute(
                "SELECT id, candidate_id, anki_note_id FROM anki_synced_cards ORDER BY id"
            )
        ),
        known_words=frozenset(conn.execute("SELECT lemma, pos FROM known_words").fetchall()),
        unknown_words=frozenset(
            str(row[0]).lower() for row in conn.execute("SELECT lemma FROM unknown_words")
        ),
        clozes=_count(conn, "SELECT count(*) FROM candidate_clozes"),
        calibration=frozenset(conn.execute("SELECT * FROM word_decisions").fetchall()),
        reports=_count(
            conn,
            "SELECT count(*) FROM card_reports WHERE candidate_id IN (SELECT id FROM candidates)",
        ),
        jobs=_count(conn, "SELECT count(*) FROM jobs"),
        phrase_jobs=_count(
            conn,
            "SELECT count(*) FROM jobs WHERE candidate_id IS NOT NULL"
            f" AND job_type IN {PHRASE_LEVEL_JOB_TYPES}",
        ),
        progress=progress,
    )


def app_export_queue(db_path: Path) -> frozenset[int]:
    """The word ids the app's ExportQueue would export from every source."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with Session(engine) as session:
            project_words(session)
            decisions = Decisions(session)
            queue = ExportQueue(
                SqlaCandidateRepository(session, SessionChangeRecorder(session)),
                SqlaOccurrenceRepository(session, SessionChangeRecorder(session)),
                decisions.word_states, decisions.vocabulary,
            )
            return frozenset(card.word_id for card in queue.for_all().pending)
    finally:
        engine.dispose()


def check_upgraded(  # noqa: C901, PLR0912, PLR0915 — one assert per §4.1 row, in its order
    conn: sqlite3.Connection, before: Before, started: datetime, finished: datetime,
    dropped_log: Iterable[int], export_queue: frozenset[int],
) -> Report:
    """`export_queue`: what the app's ExportQueue exports (`app_export_queue`)."""
    report = Report()
    phrase_of = _phrase_of_card(conn, before)
    stored_status = _has_stored_status(conn)
    words = {
        row[0]: (row[1], row[2], row[3] if stored_status else _decision_status(conn, row[0]))
        for row in conn.execute(
            f"SELECT id, lemma, pos, {'status' if stored_status else 'NULL'} FROM candidates"  # noqa: S608
        )
    }
    choices = dict(conn.execute("SELECT id, choice FROM phrases").fetchall())
    (version,) = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    orphans_only = version >= CHOICE_ON_ORPHANS_ONLY
    word_of_phrase = dict(conn.execute("SELECT id, candidate_id FROM phrases").fetchall())
    winners = before.winners()

    # phrases = old candidates; every card has its phrase
    assert _count(conn, "SELECT count(*) FROM phrases") == len(before.cards)
    assert len(phrase_of) == len(before.cards)

    # anki_synced_cards unchanged in number, every phrase_id NOT NULL
    assert _count(conn, "SELECT count(*) FROM anki_synced_cards") == len(before.rows)
    assert _count(conn, "SELECT count(*) FROM anki_synced_cards WHERE phrase_id IS NULL") == 0

    # every row's lemma / pos = its word's
    assert _count(
        conn,
        "SELECT count(*) FROM anki_synced_cards a JOIN candidates c ON c.id = a.candidate_id"
        " WHERE a.lemma != c.lemma OR a.pos IS NOT c.pos",
    ) == 0
    assert _count(
        conn, "SELECT count(*) FROM anki_synced_cards WHERE candidate_id IS NULL",
    ) == 0

    # ≤1 decision card per word
    assert _count(
        conn,
        "SELECT count(*) FROM (SELECT candidate_id FROM phrases"
        f" WHERE choice IN {DECISION_CHOICES} GROUP BY candidate_id HAVING count(*) > 1)",
    ) == 0

    # candidates.status (until 0057 drops it) == decision_status for every word; only the 4
    # values
    statuses = {status for _, _, status in words.values()}
    assert statuses <= STATUSES, statuses
    for word_id, (_, _, status) in words.items():
        assert status == _decision_status(conn, word_id), word_id

    # every card's choice and every word's status as the §4 mapping says
    for card in before.cards:
        winner = winners[card.group]
        phrase_id = phrase_of[card.id]
        actual = choices[phrase_id]
        expected = _expected_choice(card, winner, before.known)
        if expected == "skip" and actual == "none" and _released_original(conn, phrase_id):
            report.list("old SKIP: released original → NONE", card.id)
            continue
        assert actual == expected, (card, actual, expected)
        report.list(_mapping_row(card, winner, before.known, actual), card.id)

    # rows: active only on KNOWN decision cards; released rows listed by reason
    rows = {
        row[0]: (row[1], row[2], row[3], row[4], row[5], row[6])
        for row in conn.execute(
            "SELECT id, phrase_id, note_kind, learning_since, released_at, candidate_id,"
            " card_choice FROM anki_synced_cards"
        )
    }
    since_values = {since for _, _, since, _, _, _ in rows.values()}
    cards = {c.id: c for c in before.cards}
    for old in before.rows:
        phrase_id, note_kind, _, released_at, _, card_choice = rows[old.id]
        card = cards[old.card_id]
        winner = winners[card.group]
        assert phrase_id == phrase_of[card.id], old
        assert (note_kind == "cloze") is card.has_cloze, old
        # the card's choice, so an orphan tells a Known card's binding from a Learn one's;
        # later, only once the card is gone
        decided = choices[phrase_id] in DECISION_CHOICES
        copied = choices[phrase_id] if decided else note_kind
        assert card_choice == (None if orphans_only else copied), old
        active = released_at is None
        should = card is winner and card.exported and choices[phrase_id] == "known"
        assert active is should, old
        if active:
            report.list("active binding on a KNOWN card", old.id)
            assert choices[phrase_id] in {note_kind, "known"}, "A1"
        elif card is not winner:
            report.list(f"released: {MERGE_LOSER}", old.id)
        elif card.status in DECIDED:
            report.list(f"released: {KNOWN_REMOVED}", old.id)
        else:
            report.list(f"released: {NOT_DECIDED}", old.id)

    # every row's learning_since is the migration time
    assert len(since_values) <= 1, since_values
    for since in since_values:
        moment = datetime.fromisoformat(str(since))
        assert started - timedelta(seconds=1) <= moment <= finished + timedelta(seconds=1)

    # known_words, unknown_words, clozes, calibration unchanged
    _check_lists_kept(conn, before)
    assert _count(conn, "SELECT count(*) FROM candidate_clozes") == before.clozes
    assert frozenset(conn.execute("SELECT * FROM word_decisions").fetchall()) == (
        before.calibration
    )

    # choice=cloze ⇔ markup, for unbound cards with old status LEARN
    clozed = {row[0] for row in conn.execute("SELECT phrase_id FROM candidate_clozes")}
    bound = {
        row[0] for row in conn.execute(
            "SELECT phrase_id FROM anki_synced_cards WHERE released_at IS NULL"
        )
    }
    for card in before.cards:
        phrase_id = phrase_of[card.id]
        if card is winners[card.group] and card.status == "learn" and not card.exported:
            assert (choices[phrase_id] == "cloze") is (phrase_id in clozed), card
        assert phrase_id not in bound or choices[phrase_id] == "known", "A1"

    # card_reports and active phrase-level jobs keep their phrase
    # a report of a card deleted before the upgrade keeps its snapshot and has no phrase
    assert _count(
        conn,
        "SELECT count(*) FROM card_reports WHERE phrase_id IS NULL"
        " AND candidate_id IN (SELECT id FROM candidates)",
    ) == 0
    assert _count(
        conn,
        f"SELECT count(*) FROM jobs WHERE job_type IN {PHRASE_LEVEL_JOB_TYPES}"
        f" AND status IN {ACTIVE_JOB_STATUSES} AND phrase_id IS NULL",
    ) == 0
    assert _count(conn, "SELECT count(*) FROM jobs") == before.jobs
    assert _count(conn, "SELECT count(*) FROM jobs WHERE phrase_id IS NOT NULL") == (
        before.phrase_jobs
    )
    assert _count(conn, "SELECT count(*) FROM card_reports WHERE phrase_id IS NOT NULL") == (
        before.reports
    )

    # AK: no Known choice whose lemma is not in Known
    known_lower = {lemma.lower() for lemma, _ in before.known_words}
    for phrase_id, choice in choices.items():
        if choice == "known":
            lemma = words[word_of_phrase[phrase_id]][0].lower()
            assert lemma in known_lower, ("AK", phrase_id)
            assert lemma not in before.unknown_words, ("AK", phrase_id)

    # no word reads LEARNING; the timer makes nothing Known now or 30 days later
    assert not any(status == "learning" for _, _, status in words.values())
    assert _count(
        conn,
        "SELECT count(*) FROM anki_synced_cards a JOIN phrases p ON p.id = a.phrase_id"
        " WHERE a.released_at IS NULL AND p.choice != 'known'",
    ) == 0, "a timer could make a word Known"

    # no anki_notes table
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "anki_notes" not in tables

    # the dropped-decision log = the old decided merge losers
    assert sorted(dropped_log) == before.decided_losers()
    for card_id in before.decided_losers():
        report.list("merge loser with a dropped decision", card_id)

    # the export queue = the old Learn words not exported (Q15: not those now in Known)
    queue = export_queue
    expected_queue = {
        winner.id for winner in winners.values()
        if winner.status == "learn" and not winner.exported
        and winner.lemma.lower() not in before.known
    }
    assert queue == expected_queue
    report.counts["export queue"] = len(queue)
    for winner in winners.values():
        if winner.status == "learn" and not winner.exported and winner.lemma.lower() in (
            before.known
        ):
            report.list("old LEARN not exported, lemma in Known: reads Known (Q15)", winner.id)

    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

    progress: dict[int, tuple[int, int]] = {}
    for source_id, word_id, choice in conn.execute(
        "SELECT c.source_id, c.id, p.choice"
        " FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
        " WHERE p.shown_by IS NOT NULL"
    ):
        decided, total = progress.get(source_id, (0, 0))
        progress[source_id] = (
            decided + (choice != "none" or words[word_id][2] != "pending"), total + 1,
        )
    report.progress_after.update(progress)
    return report


def _has_stored_status(conn: sqlite3.Connection) -> bool:
    """`candidates.status`, the stored copy of the decision status, until 0057 drops it."""
    return "status" in {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}


def _expected_choice(card: OldCard, winner: OldCard, known: frozenset[str]) -> str:
    base = "skip" if card.status == "skip" else "none"
    if card is not winner or card.status not in DECIDED:
        return base
    lemma_known = card.lemma.lower() in known
    if card.exported or card.status == "known":
        return "known" if lemma_known else "none"
    return "cloze" if card.has_cloze else "learn"


def _mapping_row(card: OldCard, winner: OldCard, known: frozenset[str], choice: str) -> str:
    if card is not winner:
        return f"merge loser, old {card.status} → {choice.upper()}"
    exported = "exported" if card.exported else "not exported"
    lemma = "lemma in Known" if card.lemma.lower() in known else "lemma not in Known"
    if card.status in DECIDED:
        return f"old {card.status.upper()} {exported}, {lemma} → {choice.upper()}"
    return f"old {card.status.upper()} {exported} → {choice.upper()}"


def _released_original(conn: sqlite3.Connection, phrase_id: int) -> bool:
    """A card skipped for an example of its lemma: no longer shown, and its word has the
    example."""
    return _count(
        conn,
        "SELECT count(*) FROM phrases p WHERE p.id = ? AND p.shown_by IS NULL"
        " AND EXISTS (SELECT 1 FROM phrases e WHERE e.candidate_id = p.candidate_id"
        " AND e.origin = 'example')",
        (phrase_id,),
    ) == 1


def _decision_status(conn: sqlite3.Connection, word_id: int) -> str:
    row = conn.execute(
        f"SELECT p.choice, EXISTS (SELECT 1 FROM anki_synced_cards a WHERE a.phrase_id = p.id"
        f" AND a.released_at IS NULL) FROM phrases p WHERE p.candidate_id = ?"
        f" AND p.choice IN {DECISION_CHOICES}",
        (word_id,),
    ).fetchone()
    if row is None:
        return "pending"
    choice, bound = row
    if choice == "known":
        return "known"
    return "learning" if bound else "learn"


def _phrase_of_card(conn: sqlite3.Connection, before: Before) -> dict[int, int]:
    """Old card → its phrase: same word key, source phrase and position, in id order."""
    phrases: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for phrase_id, source_id, lemma, phrasal, source_phrase, position in conn.execute(
        "SELECT p.id, c.source_id, lower(c.lemma), c.is_phrasal_verb, p.source_phrase,"
        " p.phrase_position FROM phrases p JOIN candidates c ON c.id = p.candidate_id"
        " ORDER BY p.id"
    ):
        phrases[(source_id, lemma, bool(phrasal), source_phrase, position)].append(phrase_id)
    found: dict[int, int] = {}
    for card in before.cards:
        key = (*card.group, card.source_phrase, card.phrase_position)
        found[card.id] = phrases[key].pop(0)
    return found


def _count(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def _check_lists_kept(conn: sqlite3.Connection, before: Before) -> None:
    """The Known and Unknown lists as they were; once 0054 merged them into word marks,
    every lemma of either list is marked."""
    tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master")}
    if "word_marks" in tables:
        marked = frozenset(str(row[0]) for row in conn.execute("SELECT lemma FROM word_marks"))
        assert marked == (
            frozenset(lemma.lower() for lemma, _ in before.known_words) | before.unknown_words
        )
        return
    assert frozenset(conn.execute("SELECT lemma, pos FROM known_words").fetchall()) == (
        before.known_words
    )
    assert frozenset(
        str(row[0]).lower() for row in conn.execute("SELECT lemma FROM unknown_words")
    ) == before.unknown_words
