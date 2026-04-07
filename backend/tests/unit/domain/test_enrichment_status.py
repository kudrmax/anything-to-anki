from __future__ import annotations

import pytest

from backend.domain.value_objects.enrichment_status import EnrichmentStatus


@pytest.mark.unit
class TestEnrichmentStatus:
    def test_has_four_values(self) -> None:
        assert {s.value for s in EnrichmentStatus} == {"queued", "running", "done", "failed"}

    def test_string_value(self) -> None:
        assert EnrichmentStatus.DONE.value == "done"
        assert EnrichmentStatus.QUEUED.value == "queued"
        assert EnrichmentStatus.RUNNING.value == "running"
        assert EnrichmentStatus.FAILED.value == "failed"
