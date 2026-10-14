from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.domain.value_objects.note_maturity import is_mature

if TYPE_CHECKING:
    from backend.application.utils.review_status_updater import ReviewStatusUpdater
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.anki_note import AnkiNote
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.anki_note_repository import AnkiNoteRepository

logger = logging.getLogger(__name__)


class RefreshKnownFromAnki:
    """Asks Anki how the exported notes stand: a mature note makes its word Known, a deleted
    one takes its word out of learning. Each note is settled once. Expects Anki available."""

    def __init__(
        self,
        anki_connector: AnkiConnector,
        anki_note_repo: AnkiNoteRepository,
        vocabulary: UserVocabulary,
        review_status: ReviewStatusUpdater,
    ) -> None:
        self._connector = anki_connector
        self._notes = anki_note_repo
        self._vocabulary = vocabulary
        self._review_status = review_status

    def run(self) -> int:
        """How many words became Known."""
        pending = self._notes.pending()
        if not pending:
            return 0
        cards = self._connector.note_cards([note.note_id for note in pending])
        deleted = [note for note in pending if note.note_id not in cards]
        matured = [
            note for note in pending
            if note.note_id in cards and is_mature(cards[note.note_id])
        ]
        now = datetime.now(tz=UTC)
        self._notes.mark_deleted([note.note_id for note in deleted], now)
        self._notes.mark_matured([note.note_id for note in matured], now)
        known = self._promote(matured)
        changed = {note.lemma.lower() for note in (*deleted, *matured)}
        if changed:
            self._review_status.refresh_showing(changed)
        logger.info(
            "known_from_anki: done (pending=%d, matured=%d, known=%d, deleted=%d)",
            len(pending), len(matured), len(known), len(deleted),
        )
        return len(known)

    def _promote(self, matured: list[AnkiNote]) -> set[str]:
        known: set[str] = set()
        for note in matured:
            if self._vocabulary.mark_mature(note.lemma, note.pos):
                known.add(note.lemma.lower())
        return known
