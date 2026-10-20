from __future__ import annotations

from pydantic import BaseModel


class FixSectionsReportDTO(BaseModel):
    """`failed`: ids of the sources whose Rebuild did not finish."""

    phrases_stamped: int
    sources_rebuilt: int
    failed: list[int]
