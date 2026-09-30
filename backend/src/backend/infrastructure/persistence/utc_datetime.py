from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator

if TYPE_CHECKING:
    from sqlalchemy.engine import Dialect


class UTCDateTime(TypeDecorator[datetime]):
    """A timestamp stored as UTC and always loaded timezone-aware.

    SQLite has no timezone support: a plain DateTime column drops the offset
    and hands back naive values, which clients then misread as local time.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            msg = f"UTCDateTime needs a timezone-aware datetime, got naive {value!r}"
            raise ValueError(msg)
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)
