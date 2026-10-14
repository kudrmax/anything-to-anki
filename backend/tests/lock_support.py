"""A source lock for tests of manual actions: no long operation holds the source."""
from __future__ import annotations

from unittest.mock import MagicMock


def free_lock() -> MagicMock:
    lock = MagicMock()
    lock.held.return_value = None
    return lock
