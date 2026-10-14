"""Words and phrases: a card becomes a word of its source and one phrase of that word.

Revision ID: 0049
Revises: 0048

`candidates` keeps the word (one per source, lowercase lemma and phrasal-verb flag); the
phrase of every card moves to the new `phrases` table, with everything made for it
(meaning, media, tts, cloze), its jobs, export records and reports. Words of one lemma that
were separate cards merge into one word with several phrases: the duplicate's rows are
rebound to the surviving word before the duplicate is deleted, so nothing is lost.
SKIP moves from the word to its phrase; LEARN and KNOWN mark the phrase of the decision.
Anki notes already exported become `anki_notes`, mature as of this migration (they are
Known already). See docs/specs/words-phrases-rebuild.md, «Миграция 0049».

The position → occurrence key logic is a frozen copy: it must not follow later changes
of the domain's DocumentLayout.

`enrichment_cache` goes with Reprocess, its only user: Rebuild keeps everything in place.

A collected phrase keeps where its card came from (another source, or AI) on itself, so a
real phrase beside a generated one is labelled as what it is; the word no longer holds it.
A source's status becomes an outcome only: one left processing is new again, and the stage
of a running process lives with its operation in `source_operations`. Known words learn
whether Anki matured them.

One-way: merged words and re-keyed results cannot be split back into cards.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, NamedTuple

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

PHRASE_LEVEL_JOB_TYPES = ("polish", "meaning", "media", "tts")
DECIDED_STATUSES = ("learn", "known")
SKIP_STATUS = "skip"
PENDING_STATUS = "pending"
NEW_STATUS = "new"
PROCESSING_STATUS = "processing"
COLLECTED_ROLES = ("topic", "saved_phrases")
ORIGIN_AUTO = "auto"
ORIGIN_MANUAL = "manual"
ORIGIN_EXAMPLE = "example"
ORIGIN_COLLECTED = "collected"
SHOWN_BY_SELECTION = "selection"
SHOWN_BY_USER = "user"
DECISION_LEARN = "learn"
DECISION_CLOZE = "cloze"
LINE_SEPARATOR_LENGTH = 1
PHRASE_COLUMNS = ("source_phrase", "polished_phrase", "polish_reverted", "phrase_position")
# Where a collected phrase came from: now `phrases.collected_kind/collected_title`.
WORD_ORIGIN_COLUMNS = ("origin_kind", "origin_title")
WORD_INDEX_START = 0
WORD_INDEX_LEMMA = 2


class _Card(NamedTuple):
    id: int
    source_id: int
    lemma: str
    is_phrasal_verb: bool
    status: str
    exported: bool


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
    _rebuild_anki_synced_cards()
    _merge_duplicates(conn, cards)
    _release_skipped_originals(conn, cards)
    _set_decisions(conn)
    _move_ipa(conn)
    _notes_from_exports(conn, now)
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
        sa.Column("skipped", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_decision", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("decision_kind", sa.String(10), nullable=True),
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
        "anki_notes",
        sa.Column("note_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("lemma", sa.String(100), nullable=False),
        sa.Column("pos", sa.String(10), nullable=True),
        sa.Column("matured_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
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
        "known_word_removals",
        sa.Column("lemma", sa.String(100), primary_key=True),
        sa.Column("removed_at", sa.DateTime(), nullable=False),
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
    # Known words matured in Anki say so; who added the old ones is not known.
    op.add_column(
        "known_words",
        sa.Column("from_anki", sa.Boolean(), nullable=False, server_default="0"),
    )


# ── step 3: one phrase per card ───────────────────────────────────────


def _cards(conn: sa.Connection) -> list[_Card]:
    exported = {
        row[0] for row in conn.exec_driver_sql("SELECT candidate_id FROM anki_synced_cards")
    }
    return [
        _Card(
            id=row.id, source_id=row.source_id, lemma=row.lemma,
            is_phrasal_verb=bool(row.is_phrasal_verb), status=row.status,
            exported=row.id in exported,
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
                " origin, skipped, is_decision, edited_by_user, collected_kind,"
                " collected_title, created_at)"
                " VALUES (:candidate_id, :block, :line, :char, :source_phrase,"
                " :phrase_position, :polished_phrase, :polish_reverted, 0, :shown_by,"
                " :origin, :skipped, 0, 0, :collected_kind, :collected_title, :created_at)"
            ),
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
                "skipped": row.status == SKIP_STATUS,
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
    """Frozen: where the first target word starts — block, line, char.

    The phrase text is the document text from the position's start; lines of a block
    are joined by one separator character.
    """
    block, start_line, start_char = json.loads(position_json)[:3]
    phrase = json.loads(phrase_json)
    target, words = phrase["target"], phrase["words"]
    offset = words[target[0]][WORD_INDEX_START] if target and words else 0
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


def _merge_duplicates(conn: sa.Connection, cards: list[_Card]) -> None:
    groups: dict[tuple[int, str, bool], list[_Card]] = {}
    for card in cards:
        groups.setdefault((card.source_id, card.lemma.lower(), card.is_phrasal_verb), []).append(
            card
        )
    for group in groups.values():
        if len(group) < 2:  # noqa: PLR2004 — a group of one has no duplicate
            continue
        # A decision is never lost: an export record keeps its own phrase anyway.
        winner = max(
            group, key=lambda c: (c.status in DECIDED_STATUSES, c.exported, c.id),
        )
        for loser in group:
            if loser is not winner:
                _merge(conn, loser.id, winner.id)


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
                "UPDATE phrases SET skipped = 0, shown_by = NULL"
                " WHERE id = (SELECT phrase_id FROM _card_phrase WHERE candidate_id_old = :card)"
                " AND origin IN (:auto, :manual)"
                " AND EXISTS (SELECT 1 FROM phrases e WHERE e.candidate_id = phrases.candidate_id"
                " AND e.origin = :example AND e.id != phrases.id)"
            ),
            {
                "card": card.id, "example": ORIGIN_EXAMPLE, "auto": ORIGIN_AUTO,
                "manual": ORIGIN_MANUAL,
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


def _set_decisions(conn: sa.Connection) -> None:
    conn.execute(
        sa.text("UPDATE candidates SET status = :pending WHERE status = :skip"),
        {"pending": PENDING_STATUS, "skip": SKIP_STATUS},
    )
    conn.execute(
        sa.text(
            "UPDATE phrases SET is_decision = 1, skipped = 0, decision_kind = CASE"
            " WHEN EXISTS (SELECT 1 FROM candidate_clozes z"
            " WHERE z.candidate_id = phrases.candidate_id) THEN :cloze ELSE :learn END"
            f" WHERE id IN (SELECT m.phrase_id FROM _card_phrase m"
            f" JOIN candidates c ON c.id = m.candidate_id_old"
            f" WHERE c.status IN {DECIDED_STATUSES})"
        ),
        {"cloze": DECISION_CLOZE, "learn": DECISION_LEARN},
    )


# ── steps 7–11: results, ipa, notes ───────────────────────────────────


def _move_ipa(conn: sa.Connection) -> None:
    op.add_column("candidate_pronunciations", sa.Column("ipa", sa.String(100), nullable=True))
    rows = conn.execute(sa.text(
        "SELECT p.candidate_id AS word_id, mn.ipa FROM candidate_meanings mn"
        " JOIN _card_phrase m ON m.candidate_id_old = mn.candidate_id"
        " JOIN phrases p ON p.id = m.phrase_id"
        " WHERE mn.ipa IS NOT NULL AND mn.ipa != ''"
        " ORDER BY p.is_decision DESC, p.id"
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


def _notes_from_exports(conn: sa.Connection, now: datetime) -> None:
    conn.execute(
        sa.text(
            "INSERT OR IGNORE INTO anki_notes (note_id, lemma, pos, matured_at)"
            " SELECT a.anki_note_id, c.lemma, c.pos, :now FROM anki_synced_cards a"
            " JOIN candidates c ON c.id = a.candidate_id ORDER BY a.id"
        ),
        {"now": now},
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
    ) as batch:
        for column in (*PHRASE_COLUMNS, *WORD_ORIGIN_COLUMNS):
            batch.drop_column(column)
        # Unknown for old Known words: off, so undoing one never forgets a word known before.
        batch.add_column(
            sa.Column("known_added", sa.Boolean(), nullable=False, server_default="0"),
        )
        batch.add_column(
            sa.Column("was_unknown", sa.Boolean(), nullable=False, server_default="0"),
        )
    with op.batch_alter_table("jobs") as batch:
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
    with op.batch_alter_table("sources") as batch:
        batch.drop_column("processing_stage")


def _rebuild_anki_synced_cards() -> None:
    """Export records gain their phrase (kept when it goes) and lose one-per-word."""
    op.create_table(
        "_anki_synced_cards_by_phrase",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "candidate_id", sa.Integer(),
            sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "phrase_id", sa.Integer(),
            sa.ForeignKey("phrases.id", ondelete="SET NULL"), nullable=True, unique=True,
        ),
        sa.Column("anki_note_id", sa.Integer(), nullable=False),
    )
    op.execute(
        "INSERT INTO _anki_synced_cards_by_phrase (id, candidate_id, phrase_id, anki_note_id)"
        " SELECT id, candidate_id, phrase_id, anki_note_id FROM anki_synced_cards"
    )
    op.drop_table("anki_synced_cards")
    op.rename_table("_anki_synced_cards_by_phrase", "anki_synced_cards")
    op.create_index("ix_anki_synced_cards_candidate_id", "anki_synced_cards", ["candidate_id"])


# ── steps 13–14: indexes, phrase words ────────────────────────────────


def _create_indexes() -> None:
    op.create_index("ix_phrases_candidate_id", "phrases", ["candidate_id"])
    op.create_index(
        "ux_phrases_auto_key", "phrases", ["candidate_id", "block", "line", "char"],
        unique=True, sqlite_where=sa.text("origin = 'auto'"),
    )
    op.create_index(
        "ux_phrases_decision", "phrases", ["candidate_id"],
        unique=True, sqlite_where=sa.text("is_decision = 1"),
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
