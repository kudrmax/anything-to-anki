from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.ports.change_recorder import ChangeRecorder

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.domain.value_objects.card_change import CardChange

CHANGES_KEY = "change_recorder.changes"


class SessionChangeRecorder(ChangeRecorder):
    """Keeps the changes on the session, so every recorder on one session shares them.
    A write drains them when it ends. Changes recorded outside any write stay until the
    next write on the session drains them with its own."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, change: CardChange) -> None:
        self._session.info.setdefault(CHANGES_KEY, []).append(change)

    def drain(self) -> tuple[CardChange, ...]:
        changes: list[CardChange] = self._session.info.pop(CHANGES_KEY, [])
        return tuple(dict.fromkeys(changes))
