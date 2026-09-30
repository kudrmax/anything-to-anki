"""UTCDateTime: timestamps are stored as UTC and always come back timezone-aware."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from backend.infrastructure.persistence.utc_datetime import UTCDateTime
from sqlalchemy.dialects import sqlite

pytestmark = pytest.mark.unit

BANGKOK = timezone(timedelta(hours=7))
DIALECT = sqlite.dialect()


def test_aware_value_is_stored_as_utc() -> None:
    local = datetime(2026, 9, 30, 13, 46, tzinfo=BANGKOK)

    stored = UTCDateTime().process_bind_param(local, DIALECT)

    assert stored == datetime(2026, 9, 30, 6, 46)


def test_naive_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        UTCDateTime().process_bind_param(datetime(2026, 9, 30, 6, 46), DIALECT)


def test_loaded_value_is_utc_aware() -> None:
    loaded = UTCDateTime().process_result_value(datetime(2026, 9, 30, 6, 46), DIALECT)

    assert loaded == datetime(2026, 9, 30, 6, 46, tzinfo=UTC)


def test_null_passes_through() -> None:
    assert UTCDateTime().process_bind_param(None, DIALECT) is None
    assert UTCDateTime().process_result_value(None, DIALECT) is None
