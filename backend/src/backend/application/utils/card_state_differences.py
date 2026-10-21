"""Where the stored projection differs from the rows computed live: every column but the
revision; removed cards are left out."""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from backend.domain.value_objects.card_state_rows import (
        CardStateRow,
        CardStates,
        PhraseWordRow,
        StoredCardStates,
        WordStateRow,
    )

MISSING = "missing"
PRESENT = "present"
CARD_STATES = "card_states"
WORD_STATES = "word_states"
PHRASE_WORDS = "phrase_words"

type Row = CardStateRow | WordStateRow | PhraseWordRow


@dataclass(frozen=True)
class CardStateDifference:
    """One row that differs: its table and key, its lemma, and the differing columns as
    stored and as computed live (`missing` for a row on one side only)."""

    table: str
    key: str
    lemma: str
    stored: str
    live: str

    def __str__(self) -> str:
        return (
            f"{self.table} {self.key} lemma={self.lemma}:"
            f" stored {self.stored} | live {self.live}"
        )


def differences(stored: StoredCardStates, live: CardStates) -> list[CardStateDifference]:
    return [
        *_compare(
            CARD_STATES,
            {f"phrase_id={c.row.phrase_id}": c.row for c in stored.cards if not c.removed},
            {f"phrase_id={row.phrase_id}": row for row in live.cards},
        ),
        *_compare(
            WORD_STATES,
            {f"word_id={row.word_id}": row for row in stored.words},
            {f"word_id={row.word_id}": row for row in live.words},
        ),
        *_compare(
            PHRASE_WORDS,
            {f"phrase_id={r.phrase_id} position={r.position}": r for r in stored.phrase_words},
            {f"phrase_id={r.phrase_id} position={r.position}": r for r in live.phrase_words},
        ),
    ]


def _compare(
    table: str, stored: Mapping[str, Row], live: Mapping[str, Row],
) -> list[CardStateDifference]:
    found: list[CardStateDifference] = []
    for key in sorted(stored.keys() | live.keys()):
        kept, computed = stored.get(key), live.get(key)
        if kept == computed:
            continue
        if kept is None or computed is None:
            present = kept or computed
            assert present is not None
            found.append(CardStateDifference(
                table, key, present.lemma,
                stored=_presence(kept), live=_presence(computed),
            ))
            continue
        names = [
            f.name for f in fields(kept) if getattr(kept, f.name) != getattr(computed, f.name)
        ]
        found.append(CardStateDifference(
            table, key, kept.lemma,
            stored=_columns(kept, names), live=_columns(computed, names),
        ))
    return found


def _presence(row: Row | None) -> str:
    return MISSING if row is None else PRESENT


def _columns(row: Row, names: list[str]) -> str:
    return " ".join(f"{name}={getattr(row, name)!r}" for name in names)
