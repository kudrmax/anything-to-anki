from __future__ import annotations

from datetime import datetime, timedelta

LEARNING_KNOWN_AFTER_DAYS = 30
LEARNING_KNOWN_AFTER = timedelta(days=LEARNING_KNOWN_AFTER_DAYS)


def timer_due(learning_since: datetime, now: datetime) -> bool:
    """A word exported to Anki reads Known this long after that export."""
    return now - learning_since >= LEARNING_KNOWN_AFTER
