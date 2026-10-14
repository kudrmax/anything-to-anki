"""Unknown words, and a card's phrase as one object: text, words, target.

Revision ID: 0048
Revises: 0047

A card kept its phrase four ways: the text (context_fragment, polished_fragment), the
target as written (surface_form), the target's place in the document (target_position)
and a mark that the phrase was an example (has_custom_context_fragment). Now the source
phrase and the rewritten one are each text + words by characters + target by word
numbers (see docs/specs/card-phrase-model.html). fragment_unknown_count and
fragment_purity, counted once at processing, go: which words are new is decided on reading.

Carrying the cards over needs the app's language parsing, so this revision imports it.
Written for the data of the app's two copies on 2026-10-14; once applied everywhere its
body is emptied, like 0045.
"""
from __future__ import annotations

import json
import logging
from collections import Counter
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from backend.domain.services.document_layout import DocumentLayout
    from backend.domain.value_objects.phrase import Phrase
    from sqlalchemy.engine import Connection, RowMapping

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.0048")

OLD_COLUMNS = (
    "fragment_unknown_count", "fragment_purity", "context_fragment", "surface_form",
    "has_custom_context_fragment", "polished_fragment", "target_position",
)


def upgrade() -> None:
    op.create_table(
        "unknown_words",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lemma", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("candidates") as batch:
        batch.add_column(sa.Column("source_phrase", sa.Text(), nullable=True))
        batch.add_column(sa.Column("polished_phrase", sa.Text(), nullable=True))
    _carry_over(op.get_bind())
    with op.batch_alter_table("candidates") as batch:
        batch.alter_column("source_phrase", existing_type=sa.Text(), nullable=False)
        for column in OLD_COLUMNS:
            batch.drop_column(column)


def downgrade() -> None:
    raise NotImplementedError("The old phrase columns cannot be rebuilt from card phrases")


def _carry_over(bind: Connection) -> None:
    rows = bind.execute(sa.text(
        "SELECT id, source_id, lemma, context_fragment, surface_form, polished_fragment,"
        " phrase_position, target_position FROM candidates",
    )).mappings().all()
    if not rows:
        return
    from backend.domain.exceptions import TargetNotInPhraseError
    from backend.domain.services.document_layout import DocumentLayout
    from backend.domain.services.phrase_building import word_spans
    from backend.infrastructure.container import Container
    from backend.infrastructure.persistence.models import dump_phrase, load_position
    from backend.infrastructure.persistence.sqla_document_repository import (
        SqlaDocumentRepository,
    )
    from sqlalchemy.orm import Session

    reader = Container().phrase_reader
    documents = SqlaDocumentRepository(Session(bind=bind))
    layouts: dict[int, DocumentLayout | None] = {}
    counts: Counter[str] = Counter()

    def layout_of(source_id: int) -> DocumentLayout | None:
        if source_id not in layouts:
            document = documents.get(source_id)
            layouts[source_id] = DocumentLayout(document) if document else None
        return layouts[source_id]

    def by_lemma(text: str, *names: str | None) -> Phrase | None:
        for name in names:
            if not name:
                continue
            try:
                return reader.read_for(text, name)
            except TargetNotInPhraseError:
                continue
        return None

    def source_phrase(row: RowMapping) -> Phrase:
        text = row["context_fragment"]
        layout = layout_of(row["source_id"])
        place = load_position(row["phrase_position"])
        target = load_position(row["target_position"])
        if layout is not None and place is not None and target is not None:
            start, _ = layout.span(place)
            t_start, t_end = layout.span(target)
            if _same_text(layout.fragment(place), text):
                try:
                    spans = _target_spans(text, t_start - start, t_end - start)
                    phrase = reader.read(text, spans)
                    counts["target_from_document"] += 1
                    return _whole_target(phrase, row["lemma"])
                except TargetNotInPhraseError:
                    pass
        found = by_lemma(text, row["surface_form"], row["lemma"])
        if found is not None:
            counts["target_by_form"] += 1
            return found
        counts["target_first_word"] += 1
        logger.warning("0048: target not found, first word taken (candidate=%s)", row["id"])
        spans = word_spans(text) or [(0, len(text))]
        return reader.read(text, [spans[0]])

    cloze_rows = {
        r["candidate_id"]: r for r in bind.execute(sa.text(
            "SELECT candidate_id, hidden_word_indices, phrase FROM candidate_clozes",
        )).mappings()
    }
    for row in rows:
        source = source_phrase(row)
        polished: Phrase | None = None
        if row["polished_fragment"] is not None:
            if row["polished_fragment"] == source.text:
                polished = source
            else:
                polished = by_lemma(row["polished_fragment"], row["lemma"], row["surface_form"])
                counts["polished_kept" if polished else "polished_dropped"] += 1
        bind.execute(
            sa.text(
                "UPDATE candidates SET source_phrase = :s, polished_phrase = :p WHERE id = :id",
            ),
            {"s": dump_phrase(source), "p": dump_phrase(polished), "id": row["id"]},
        )
        cloze = cloze_rows.get(row["id"])
        if cloze is not None:
            for phrase in (polished, source):
                if phrase is not None and phrase.text == cloze["phrase"]:
                    old = json.loads(cloze["hidden_word_indices"])
                    indices = _new_indices(phrase, cloze["phrase"], old) or list(phrase.target)
                    bind.execute(
                        sa.text(
                            "UPDATE candidate_clozes SET hidden_word_indices = :h"
                            " WHERE candidate_id = :id",
                        ),
                        {"h": json.dumps(indices), "id": row["id"]},
                    )
                    counts["cloze_moved"] += 1
                    break
    logger.info("0048: carried %d cards over: %s", len(rows), dict(counts))


def _whole_target(phrase: Phrase, lemma: str) -> Phrase:
    """The old position kept only the target's first and last words; the middle of
    "catch up on" is found by the lemma between them."""
    from backend.domain.services.phrase_building import target_by_lemma

    first, last = phrase.target[0], phrase.target[-1]
    found = target_by_lemma(phrase.words[first:last + 1], phrase.text, lemma)
    if len(found) <= len(phrase.target):
        return phrase
    return phrase.with_target(tuple(first + i for i in found))


def _same_text(fragment: str, text: str) -> bool:
    """The document joins a phrase's lines with spaces where the old phrase kept line
    breaks; the characters still stand in the same places."""
    return len(fragment) == len(text) and fragment.split() == text.split()


def _target_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """The old target position ran from its first word to its last ("give it up"): its
    first and last words are the target."""
    from backend.domain.services.phrase_building import word_spans

    inside = [(s, e) for s, e in word_spans(text) if s < end and start < e]
    return [inside[0], inside[-1]] if len(inside) > 1 else inside


def _new_indices(phrase: Phrase, text: str, old: list[int]) -> list[int]:
    """Old numbers counted words by spaces; a new word is hidden if it lies in a hidden one."""
    pieces: list[tuple[int, int]] = []
    position = 0
    for piece in text.split():
        start = text.index(piece, position)
        pieces.append((start, start + len(piece)))
        position = start + len(piece)
    hidden = [pieces[i] for i in old if 0 <= i < len(pieces)]
    return [
        i for i, word in enumerate(phrase.words)
        if any(s <= word.start and word.end <= e for s, e in hidden)
    ]
