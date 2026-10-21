from __future__ import annotations

from datetime import datetime, timedelta

LEARNING_KNOWN_AFTER_DAYS = 30
LEARNING_KNOWN_AFTER = timedelta(days=LEARNING_KNOWN_AFTER_DAYS)


def timer_due(learning_since: datetime, now: datetime) -> bool:
    """A word exported to Anki reads Known this long after that export."""
    return now - learning_since >= LEARNING_KNOWN_AFTER


def known_on(learning_since: datetime) -> datetime:
    """When a word exported at `learning_since` reads Known."""
    return learning_since + LEARNING_KNOWN_AFTER


def exported_for_due(after: datetime | None, until: datetime) -> tuple[datetime | None, datetime]:
    """The exports whose timer comes due after `after` (any time when None) and by `until`:
    those after the first moment returned and by the second."""
    return (
        None if after is None else after - LEARNING_KNOWN_AFTER,
        until - LEARNING_KNOWN_AFTER,
    )
