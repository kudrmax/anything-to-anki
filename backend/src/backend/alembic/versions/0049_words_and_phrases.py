"""Words and phrases: a card becomes a word of its source and one phrase of that word.

Revision ID: 0049
Revises: 0048

`candidates` keeps the word (one per source, lowercase lemma and phrasal-verb flag); the
phrase of every card moves to the new `phrases` table, with everything made for it
(meaning, media, tts, cloze), its jobs, export records and reports. Words of one lemma that
were separate cards merge into one word with several phrases: the duplicate's rows are
rebound to the surviving word before the duplicate is deleted, so nothing is lost.
Each card gets one choice (none / learn / cloze / known / skip): SKIP moves from the word to
its phrase, and LEARN and KNOWN become the choice of the word's decision card. The word's
status is the decision status (pending / learn / learning / known). An export record is the
card's binding to its Anki note: it gets the lemma, POS and note kind, and stays active only
on a Known card whose lemma is still in Known; every other is released at migration (the user
removed Known, or the card was not decided). See docs/specs/words-phrases-rebuild.md and the
status-model design, §4.

The position → occurrence key logic is a frozen copy: it must not follow later changes
of the domain's DocumentLayout.

`enrichment_cache` goes with Reprocess, its only user: Rebuild keeps everything in place.

A collected phrase keeps where its card came from (another source, or AI) on itself, so a
real phrase beside a generated one is labelled as what it is; the word no longer holds it.
A source's status becomes an outcome only: one left processing is new again, and the stage
of a running process lives with its operation in `source_operations`.

One-way: merged words and re-keyed results cannot be split back into cards.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, NamedTuple

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)

PHRASE_LEVEL_JOB_TYPES = ("polish", "meaning", "media", "tts")
DECIDED_STATUSES = ("learn", "known")
LEARN_STATUS = "learn"
KNOWN_STATUS = "known"
SKIP_STATUS = "skip"
PENDING_STATUS = "pending"
CHOICE_NONE = "none"
CHOICE_LEARN = "learn"
CHOICE_CLOZE = "cloze"
CHOICE_KNOWN = "known"
CHOICE_SKIP = "skip"
DECISION_CHOICES = (CHOICE_LEARN, CHOICE_CLOZE, CHOICE_KNOWN)
NOTE_KIND_LEARN = "learn"
NOTE_KIND_CLOZE = "cloze"
STATUS_OF_CHOICE = {
    CHOICE_LEARN: LEARN_STATUS, CHOICE_CLOZE: LEARN_STATUS, CHOICE_KNOWN: KNOWN_STATUS,
}
DROPPED_DECISION_LOG = "0049: merge dropped the %s decision of card %d (lemma %r, word %d)"
NEW_STATUS = "new"
PROCESSING_STATUS = "processing"
COLLECTED_ROLES = ("topic", "saved_phrases")
ORIGIN_AUTO = "auto"
ORIGIN_MANUAL = "manual"
ORIGIN_EXAMPLE = "example"
ORIGIN_COLLECTED = "collected"
SHOWN_BY_SELECTION = "selection"
SHOWN_BY_USER = "user"
LINE_SEPARATOR_LENGTH = 1
PHRASE_COLUMNS = ("source_phrase", "polished_phrase", "polish_reverted", "phrase_position")
# Where a collected phrase came from: now `phrases.collected_kind/collected_title`.
WORD_ORIGIN_COLUMNS = ("origin_kind", "origin_title")
# Batch operations reflect only the table they rebuild: following its foreign keys would
# reflect `collections`, whose expression index SQLAlchemy can't read.
OWN_TABLE_ONLY = {"resolve_fks": False}
WORD_INDEX_START = 0
WORD_INDEX_LEMMA = 2


class _Card(NamedTuple):
    id: int
    source_id: int
    lemma: str
    is_phrasal_verb: bool
    status: str
    exported: bool
    latest_synced_row: int  # 0 without one

    @property
    def merge_rank(self) -> tuple[bool, int, bool, bool, int]:
        """The winner of a merge: an exported card, then the latest export, then a decision
        (skip is none), Known over Learn, then the newest."""
        return (
            self.exported, self.latest_synced_row, self.status in DECIDED_STATUSES,
            self.status == KNOWN_STATUS, self.id,
        )


def upgrade() -> None:
    conn = op.get_bind()
    assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 0, (
        "Migration 0049 rebinds rows before deleting merged words: foreign keys must be off"
    )
    now = datetime.now(tz=UTC).replace(tzinfo=None)

    _create_tables()
    _add_phrase_columns()
    cards = _cards(conn)
    _create_phrases(conn, now)
    _fill_phrase_ids(conn)
    _rebuild_anki_synced_cards(now)
    winners = _merge_duplicates(conn, cards)
    _rows_follow_their_word(conn)
    _release_skipped_originals(conn, cards)
    _set_decisions(conn, winners, now)
    _move_ipa(conn)
    _rekey_results()
    _drop_card_columns()
    _sources_without_processing(conn)
    _create_indexes()
    _fill_phrase_words(conn)
    op.drop_table("_card_phrase")
    op.drop_table("enrichment_cache")


def downgrade() -> None:
    raise NotImplementedError("Merged words and phrase-keyed results cannot be split into cards")


# ── step 2: tables ────────────────────────────────────────────────────


def _create_tables() -> None:
    op.create_table(
        "phrases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "candidate_id", sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("block", sa.Integer(), nullable=True),
        sa.Column("line", sa.Integer(), nullable=True),
        sa.Column("char", sa.Integer(), nullable=True),
        sa.Column("source_phrase", sa.Text(), nullable=False),
        sa.Column("phrase_position", sa.Text(), nullable=True),
        sa.Column("polished_phrase", sa.Text(), nullable=True),
        sa.Column("polish_reverted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("fragment_score", sa.Float(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shown_by", sa.String(10), nullable=True),
        sa.Column("origin", sa.String(10), nullable=False),
        sa.Column("choice", sa.String(10), nullable=False, server_default=CHOICE_NONE),
        sa.Column("edited_by_user", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("replaces_selection", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("collected_kind", sa.String(10), nullable=True),
        sa.Column("collected_title", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "phrase_words",
        sa.Column(
            "phrase_id", sa.Integer(),
            sa.ForeignKey("phrases.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("lemma", sa.String(100), primary_key=True),
    )
    op.create_table(
        "document_parses",
        sa.Column("document_hash", sa.String(64), primary_key=True),
        sa.Column("analyzer_version", sa.String(60), primary_key=True),
        sa.Column("tokens", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "source_operations",
        sa.Column(
            "source_id", sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True,
            autoincrement=False,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(30), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "_card_phrase",
        sa.Column("candidate_id_old", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("phrase_id", sa.Integer(), nullable=False),
    )


def _add_phrase_columns() -> None:
    op.add_column("jobs", sa.Column("phrase_id", sa.Integer(), nullable=True))
    op.add_column("jobs", sa.Column("phrase_revision", sa.Integer(), nullable=True))
    op.add_column("card_reports", sa.Column("phrase_id", sa.Integer(), nullable=True))
    op.add_column("anki_synced_cards", sa.Column("phrase_id", sa.Integer(), nullable=True))


# ── step 3: one phrase per card ───────────────────────────────────────


def _cards(conn: sa.Connection) -> list[_Card]:
    latest: dict[int, int] = {
        int(row[0]): int(row[1]) for row in conn.exec_driver_sql(
            "SELECT candidate_id, max(id) FROM anki_synced_cards GROUP BY candidate_id"
        )
    }
    return [
        _Card(
            id=row.id, source_id=row.source_id, lemma=row.lemma,
            is_phrasal_verb=bool(row.is_phrasal_verb), status=row.status,
            exported=row.id in latest, latest_synced_row=latest.get(row.id, 0),
        )
        for row in conn.execute(sa.text(
            "SELECT id, source_id, lemma, is_phrasal_verb, status FROM candidates ORDER BY id"
        ))
    ]


def _create_phrases(conn: sa.Connection, now: datetime) -> None:
    documents = {
        row.source_id: _line_lengths(row.document)
        for row in conn.execute(sa.text("SELECT source_id, document FROM source_documents"))
    }
    rows = conn.execute(sa.text(
        "SELECT c.id, c.source_id, c.status, c.source_phrase, c.polished_phrase,"
        " c.polish_reverted, c.phrase_position, c.origin_kind, c.origin_title, s.role"
        " FROM candidates c JOIN sources s ON s.id = c.source_id ORDER BY c.id"
    )).all()
    for row in rows:
        origin = _origin(row.role, row.phrase_position)
        key = (
            _target_key(row.phrase_position, row.source_phrase, documents.get(row.source_id, {}))
            if origin == ORIGIN_AUTO
            else None
        )
        inserted = conn.execute(
            sa.text(
                "INSERT INTO phrases (candidate_id, block, line, char, source_phrase,"
                " phrase_position, polished_phrase, polish_reverted, revision, shown_by,"
                " origin, choice, edited_by_user, collected_kind,"
                " collected_title, created_at)"
                " VALUES (:candidate_id, :block, :line, :char, :source_phrase,"
                " :phrase_position, :polished_phrase, :polish_reverted, 0, :shown_by,"
                " :origin, :choice, 0, :collected_kind, :collected_title, :created_at)"
            ).bindparams(sa.bindparam("created_at", type_=sa.DateTime())),
            {
                "candidate_id": row.id,
                "block": key[0] if key else None,
                "line": key[1] if key else None,
                "char": key[2] if key else None,
                "source_phrase": row.source_phrase,
                "phrase_position": row.phrase_position,
                "polished_phrase": row.polished_phrase,
                "polish_reverted": row.polish_reverted,
                "shown_by": SHOWN_BY_SELECTION if origin == ORIGIN_AUTO else SHOWN_BY_USER,
                "origin": origin,
                "choice": CHOICE_SKIP if row.status == SKIP_STATUS else CHOICE_NONE,
                "collected_kind": row.origin_kind,
                "collected_title": row.origin_title,
                "created_at": now,
            },
        )
        conn.execute(
            sa.text("INSERT INTO _card_phrase (candidate_id_old, phrase_id) VALUES (:c, :p)"),
            {"c": row.id, "p": inserted.lastrowid},
        )


def _origin(role: str, phrase_position: str | None) -> str:
    if role in COLLECTED_ROLES:
        return ORIGIN_COLLECTED
    if phrase_position is None:
        return ORIGIN_EXAMPLE
    return ORIGIN_AUTO


def _line_lengths(document_json: str) -> dict[int, list[int]]:
    """Frozen: the length of every line of every block of a stored document."""
    lengths: dict[int, list[int]] = {}
    for index, block in enumerate(json.loads(document_json)["blocks"]):
        if block["type"] == "heading":
            lengths[index] = [len(block["text"])]
        else:
            lengths[index] = [len(line["text"]) for line in block["lines"]]
    return lengths


def _target_key(
    position_json: str, phrase_json: str, lengths: dict[int, list[int]],
) -> tuple[int, int, int]:
    """Frozen: where the first target word starts — block, line, char — by the rule the
    analysis keys an occurrence with (the earliest target word, as DocumentLayout.target_key).

    The phrase text is the document text from the position's start; lines of a block
    are joined by one separator character.
    """
    block, start_line, start_char = json.loads(position_json)[:3]
    phrase = json.loads(phrase_json)
    target, words = phrase["target"], phrase["words"]
    offset = min(words[i][WORD_INDEX_START] for i in target) if target and words else 0
    line, char = start_line, start_char + offset
    block_lines = lengths.get(block, [])
    while line < len(block_lines) - 1 and char >= block_lines[line]:
        char -= block_lines[line] + LINE_SEPARATOR_LENGTH
        line += 1
    return block, line, char


def _fill_phrase_ids(conn: sa.Connection) -> None:
    """Before any merge rebinds them, jobs, reports and exports learn their card's phrase."""
    phrase_of_card = (
        "(SELECT phrase_id FROM _card_phrase WHERE candidate_id_old = {}.candidate_id)"
    )
    conn.execute(sa.text(
        f"UPDATE jobs SET phrase_id = {phrase_of_card.format('jobs')}, phrase_revision = 0"
        f" WHERE job_type IN {PHRASE_LEVEL_JOB_TYPES} AND candidate_id IS NOT NULL"
    ))
    conn.execute(sa.text(
        f"UPDATE card_reports SET phrase_id = {phrase_of_card.format('card_reports')}"
    ))
    conn.execute(sa.text(
        f"UPDATE anki_synced_cards SET phrase_id = {phrase_of_card.format('anki_synced_cards')}"
    ))


# ── step 4: words of one lemma merge ──────────────────────────────────


def _merge_duplicates(conn: sa.Connection, cards: list[_Card]) -> list[_Card]:
    """The winner of every group of one lemma; the losers merge into it. A loser's decision
    is dropped and logged: the word keeps one decision, the winner's."""
    groups: dict[tuple[int, str, bool], list[_Card]] = {}
    for card in cards:
        groups.setdefault((card.source_id, card.lemma.lower(), card.is_phrasal_verb), []).append(
            card
        )
    winners: list[_Card] = []
    for group in groups.values():
        winner = max(group, key=lambda c: c.merge_rank)
        winners.append(winner)
        for loser in group:
            if loser is winner:
                continue
            if loser.status in DECIDED_STATUSES:
                logger.warning(
                    DROPPED_DECISION_LOG, loser.status, loser.id, loser.lemma, winner.id,
                )
            _merge(conn, loser.id, winner.id)
    return winners


def _merge(conn: sa.Connection, loser: int, winner: int) -> None:
    params = {"loser": loser, "winner": winner}
    conn.execute(
        sa.text(
            "UPDATE phrases SET origin = :manual, shown_by = :user"
            " WHERE candidate_id = :loser AND origin = :auto"
        ),
        {**params, "manual": ORIGIN_MANUAL, "user": SHOWN_BY_USER, "auto": ORIGIN_AUTO},
    )
    for table in ("phrases", "jobs", "anki_synced_cards", "card_reports"):
        conn.execute(
            sa.text(f"UPDATE {table} SET candidate_id = :winner WHERE candidate_id = :loser"),  # noqa: S608 — fixed table names
            params,
        )
    for table in ("candidate_pronunciations", "candidate_meaning_images"):
        winner_has = conn.execute(
            sa.text(f"SELECT 1 FROM {table} WHERE candidate_id = :winner"), params,  # noqa: S608
        ).first()
        if winner_has:
            conn.execute(sa.text(f"DELETE FROM {table} WHERE candidate_id = :loser"), params)  # noqa: S608
        else:
            conn.execute(
                sa.text(f"UPDATE {table} SET candidate_id = :winner WHERE candidate_id = :loser"),  # noqa: S608
                params,
            )
    conn.execute(sa.text("DELETE FROM cefr_breakdowns WHERE candidate_id = :loser"), params)
    conn.execute(sa.text("DELETE FROM candidates WHERE id = :loser"), params)


# ── steps 5–6: skips and decisions ────────────────────────────────────


def _release_skipped_originals(conn: sa.Connection, cards: list[_Card]) -> None:
    """A card skipped for an example of its lemma: the original is neither skipped nor shown.

    It is again the analyzer's phrase of its place, even when the merge made it a duplicate,
    unless another phrase of the word holds that place.
    """
    for card in cards:
        if card.status != SKIP_STATUS:
            continue
        released = conn.execute(
            sa.text(
                "UPDATE phrases SET choice = :none, shown_by = NULL"
                " WHERE id = (SELECT phrase_id FROM _card_phrase WHERE candidate_id_old = :card)"
                " AND origin IN (:auto, :manual)"
                " AND EXISTS (SELECT 1 FROM phrases e WHERE e.candidate_id = phrases.candidate_id"
                " AND e.origin = :example AND e.id != phrases.id)"
            ),
            {
                "card": card.id, "example": ORIGIN_EXAMPLE, "auto": ORIGIN_AUTO,
                "manual": ORIGIN_MANUAL, "none": CHOICE_NONE,
            },
        )
        if not released.rowcount:
            continue
        conn.execute(
            sa.text(
                "UPDATE phrases SET replaces_selection = 1"
                " WHERE origin = :example AND shown_by IS NOT NULL AND candidate_id ="
                " (SELECT p.candidate_id FROM phrases p JOIN _card_phrase c ON c.phrase_id = p.id"
                " WHERE c.candidate_id_old = :card)"
            ),
            {"card": card.id, "example": ORIGIN_EXAMPLE},
        )
        conn.execute(
            sa.text(
                "UPDATE phrases SET origin = :auto"
                " WHERE id = (SELECT phrase_id FROM _card_phrase WHERE candidate_id_old = :card)"
                " AND origin = :manual AND block IS NOT NULL"
                " AND NOT EXISTS (SELECT 1 FROM phrases o"
                " WHERE o.candidate_id = phrases.candidate_id AND o.origin = :auto"
                " AND o.id != phrases.id AND o.block = phrases.block"
                " AND o.line = phrases.line AND o.char = phrases.char)"
            ),
            {"card": card.id, "auto": ORIGIN_AUTO, "manual": ORIGIN_MANUAL},
        )


def _set_decisions(conn: sa.Connection, winners: list[_Card], now: datetime) -> None:
    """The decision of a word is its winner's, on the winner's own card (design §4).

    An exported winner keeps its Known only while the lemma is still in Known: then the card
    is the Known decision and its export stays active. Otherwise the user removed Known after
    that export, so the word is new and the export is released. Every other export record of
    the word — of a loser, or of a card without a decision — is released too. A Learn not
    exported is a cloze when the card has cloze markup; a Known whose lemma is no longer in
    Known is no decision. Unknown wins over Known.
    """
    known = _lemmas(conn, "known_words") - _lemmas(conn, "unknown_words")
    for winner in winners:
        phrase_id = conn.execute(
            sa.text("SELECT phrase_id FROM _card_phrase WHERE candidate_id_old = :card"),
            {"card": winner.id},
        ).scalar_one()
        choice = _decision_choice(conn, winner, winner.lemma.lower() in known)
        if choice is not None:
            conn.execute(
                sa.text("UPDATE phrases SET choice = :choice WHERE id = :phrase"),
                {"choice": choice, "phrase": phrase_id},
            )
        conn.execute(
            sa.text("UPDATE candidates SET status = :status WHERE id = :word"),
            {
                "status": STATUS_OF_CHOICE.get(choice or CHOICE_NONE, PENDING_STATUS),
                "word": winner.id,
            },
        )
        active_phrase = phrase_id if choice == CHOICE_KNOWN and winner.exported else None
        conn.execute(
            sa.text(
                "UPDATE anki_synced_cards SET released_at = :now"
                " WHERE candidate_id = :word AND phrase_id IS NOT :active"
            ).bindparams(sa.bindparam("now", type_=sa.DateTime())),
            {"now": now, "word": winner.id, "active": active_phrase},
        )


def _decision_choice(conn: sa.Connection, winner: _Card, lemma_known: bool) -> str | None:
    """The winner card's new choice; None keeps the one it was made with (skip or none).

    The cloze marker is the winner's own old card's markup, read before results move to
    phrases."""
    if winner.status not in DECIDED_STATUSES:
        return None
    if winner.exported or winner.status == KNOWN_STATUS:
        return CHOICE_KNOWN if lemma_known else CHOICE_NONE
    has_markup = conn.execute(
        sa.text("SELECT 1 FROM candidate_clozes WHERE candidate_id = :card"),
        {"card": winner.id},
    ).first()
    return CHOICE_CLOZE if has_markup else CHOICE_LEARN


def _lemmas(conn: sa.Connection, table: str) -> set[str]:
    return {
        str(row[0]).lower()
        for row in conn.execute(sa.text(f"SELECT lemma FROM {table}"))  # noqa: S608 — fixed names
    }


# ── steps 7–11: results, ipa, notes ───────────────────────────────────


def _move_ipa(conn: sa.Connection) -> None:
    op.add_column("candidate_pronunciations", sa.Column("ipa", sa.String(100), nullable=True))
    rows = conn.execute(sa.text(
        "SELECT p.candidate_id AS word_id, mn.ipa FROM candidate_meanings mn"
        " JOIN _card_phrase m ON m.candidate_id_old = mn.candidate_id"
        " JOIN phrases p ON p.id = m.phrase_id"
        " WHERE mn.ipa IS NOT NULL AND mn.ipa != ''"
        f" ORDER BY p.choice IN {DECISION_CHOICES} DESC, p.id"
    )).all()
    seen: set[int] = set()
    for row in rows:
        if row.word_id in seen:
            continue
        seen.add(row.word_id)
        params = {"word": row.word_id, "ipa": row.ipa}
        exists = conn.execute(
            sa.text("SELECT 1 FROM candidate_pronunciations WHERE candidate_id = :word"), params,
        ).first()
        if exists:
            conn.execute(
                sa.text(
                    "UPDATE candidate_pronunciations SET ipa = :ipa WHERE candidate_id = :word"
                ),
                params,
            )
        else:
            conn.execute(
                sa.text(
                    "INSERT INTO candidate_pronunciations (candidate_id, ipa) VALUES (:word, :ipa)"
                ),
                params,
            )


def _rekey_results() -> None:
    _rekey(
        "candidate_meanings",
        [
            sa.Column("meaning", sa.Text(), nullable=True),
            sa.Column("translation", sa.Text(), nullable=True),
            sa.Column("synonyms", sa.Text(), nullable=True),
            sa.Column("examples", sa.Text(), nullable=True),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
        ],
    )
    _rekey(
        "candidate_media",
        [
            sa.Column("screenshot_path", sa.Text(), nullable=True),
            sa.Column("audio_path", sa.Text(), nullable=True),
            sa.Column("start_ms", sa.Integer(), nullable=True),
            sa.Column("end_ms", sa.Integer(), nullable=True),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
        ],
    )
    _rekey(
        "candidate_tts",
        [
            sa.Column("audio_path", sa.Text(), nullable=True),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
        ],
    )
    _rekey(
        "candidate_clozes",
        [
            sa.Column("hidden_word_indices", sa.Text(), nullable=False),
            sa.Column("hint_kind", sa.String(20), nullable=False),
            sa.Column("custom_hint", sa.Text(), nullable=True),
            sa.Column("phrase", sa.Text(), nullable=False),
        ],
    )


# Any: the result columns are of mixed types.
def _rekey(table: str, columns: list[sa.Column[Any]]) -> None:
    """Results of a card move to its phrase: the table is rebuilt keyed by phrase_id."""
    new_table = f"_{table}_by_phrase"
    op.create_table(
        new_table,
        sa.Column(
            "phrase_id", sa.Integer(), sa.ForeignKey("phrases.id", ondelete="CASCADE"),
            primary_key=True, autoincrement=False,
        ),
        *columns,
    )
    names = ", ".join(c.name for c in columns)
    selected = ", ".join(f"r.{c.name}" for c in columns)
    op.execute(
        f"INSERT INTO {new_table} (phrase_id, {names})"  # noqa: S608 — fixed names
        f" SELECT m.phrase_id, {selected} FROM {table} r"
        " JOIN _card_phrase m ON m.candidate_id_old = r.candidate_id"
    )
    op.drop_table(table)
    op.rename_table(new_table, table)


# ── step 12: drop moved columns ───────────────────────────────────────


def _drop_card_columns() -> None:
    with op.batch_alter_table(
        "candidates", recreate="always", table_kwargs={"sqlite_autoincrement": True},
        reflect_kwargs=OWN_TABLE_ONLY,
    ) as batch:
        for column in (*PHRASE_COLUMNS, *WORD_ORIGIN_COLUMNS):
            batch.drop_column(column)
    with op.batch_alter_table("jobs", reflect_kwargs=OWN_TABLE_ONLY) as batch:
        batch.create_foreign_key(
            "fk_jobs_phrase_id_phrases", "phrases", ["phrase_id"], ["id"], ondelete="CASCADE",
        )
        batch.create_index("ix_jobs_phrase_id", ["phrase_id"])


def _sources_without_processing(conn: sa.Connection) -> None:
    """A source's status is an outcome, not a lock: one left processing is new again, as the
    startup reset made it; the stage of a running process lives with its operation."""
    conn.execute(
        sa.text("UPDATE sources SET status = :new WHERE status = :processing"),
        {"new": NEW_STATUS, "processing": PROCESSING_STATUS},
    )
    with op.batch_alter_table("sources", reflect_kwargs=OWN_TABLE_ONLY) as batch:
        batch.drop_column("processing_stage")


def _rebuild_anki_synced_cards(now: datetime) -> None:
    """Export records become the bindings of cards to their notes: the only note table.

    A record gains its phrase, the lemma and POS of its word, and its note kind: a cloze
    exactly when its own old card had cloze markup. A record is never deleted: it outlives
    its card and its word (SET NULL). Its timer starts at the migration, since the old app
    kept no export date; it is read only on an active binding, and every active one ends on a
    Known card. Released ones stay as history.
    """
    op.create_table(
        "_anki_synced_cards_by_phrase",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "candidate_id", sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "phrase_id", sa.Integer(),
            sa.ForeignKey("phrases.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("anki_note_id", sa.Integer(), nullable=False),
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column("pos", sa.String(10), nullable=True),
        sa.Column("note_kind", sa.String(10), nullable=False),
        sa.Column("learning_since", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
    )
    op.get_bind().execute(
        sa.text(
            "INSERT INTO _anki_synced_cards_by_phrase (id, candidate_id, phrase_id,"
            " anki_note_id, lemma, pos, note_kind, learning_since)"
            " SELECT a.id, a.candidate_id, a.phrase_id, a.anki_note_id, c.lemma, c.pos,"
            " CASE WHEN EXISTS (SELECT 1 FROM candidate_clozes z"
            " WHERE z.candidate_id = a.candidate_id) THEN :cloze ELSE :learn END, :now"
            " FROM anki_synced_cards a JOIN candidates c ON c.id = a.candidate_id"
        ).bindparams(sa.bindparam("now", type_=sa.DateTime())),
        {"cloze": NOTE_KIND_CLOZE, "learn": NOTE_KIND_LEARN, "now": now},
    )
    op.drop_table("anki_synced_cards")
    op.rename_table("_anki_synced_cards_by_phrase", "anki_synced_cards")
    op.create_index("ix_anki_synced_cards_candidate_id", "anki_synced_cards", ["candidate_id"])
    op.create_index("ix_anki_synced_cards_phrase_id", "anki_synced_cards", ["phrase_id"])
    op.create_index("ix_anki_synced_cards_lemma", "anki_synced_cards", ["lemma"])
    op.create_index(
        "ux_anki_synced_cards_active", "anki_synced_cards", ["phrase_id"],
        unique=True, sqlite_where=sa.text("released_at IS NULL AND phrase_id IS NOT NULL"),
    )


def _rows_follow_their_word(conn: sa.Connection) -> None:
    """After the merge an export record takes the lemma and POS of the word it ended in."""
    conn.execute(sa.text(
        "UPDATE anki_synced_cards SET"
        " lemma = (SELECT c.lemma FROM candidates c WHERE c.id = anki_synced_cards.candidate_id),"
        " pos = (SELECT c.pos FROM candidates c WHERE c.id = anki_synced_cards.candidate_id)"
    ))


# ── steps 13–14: indexes, phrase words ────────────────────────────────


def _create_indexes() -> None:
    op.create_index("ix_phrases_candidate_id", "phrases", ["candidate_id"])
    op.create_index(
        "ux_phrases_auto_key", "phrases", ["candidate_id", "block", "line", "char"],
        unique=True, sqlite_where=sa.text("origin = 'auto'"),
    )
    op.create_index(
        "ux_phrases_decision", "phrases", ["candidate_id"],
        unique=True, sqlite_where=sa.text(f"choice IN {DECISION_CHOICES}"),
    )
    op.create_index(
        "ux_candidates_word", "candidates",
        ["source_id", sa.text("lower(lemma)"), "is_phrasal_verb"], unique=True,
    )
    op.create_index("ix_phrase_words_lemma", "phrase_words", ["lemma", "phrase_id"])


def _fill_phrase_words(conn: sa.Connection) -> None:
    """The words of the text each phrase shows: the polished one unless it was reverted."""
    rows = conn.execute(sa.text(
        "SELECT id, source_phrase, polished_phrase, polish_reverted FROM phrases"
    )).all()
    for row in rows:
        shown = (
            row.polished_phrase
            if row.polished_phrase is not None and not row.polish_reverted
            else row.source_phrase
        )
        lemmas = sorted({
            word[WORD_INDEX_LEMMA].lower() for word in json.loads(shown)["words"]
        })
        if lemmas:
            conn.execute(
                sa.text("INSERT INTO phrase_words (phrase_id, lemma) VALUES (:p, :l)"),
                [{"p": row.id, "l": lemma} for lemma in lemmas],
            )
