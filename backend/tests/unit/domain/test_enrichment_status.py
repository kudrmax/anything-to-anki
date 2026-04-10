from __future__ import annotations

import pytest
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


@pytest.mark.unit
class TestEnrichmentStatus:
    def test_has_expected_values(self) -> None:
        assert {s.value for s in EnrichmentStatus} == {
            "idle", "queued", "running", "done", "failed", "cancelled"
        }

    def test_string_value(self) -> None:
        assert EnrichmentStatus.IDLE.value == "idle"
        assert EnrichmentStatus.DONE.value == "done"
        assert EnrichmentStatus.QUEUED.value == "queued"
        assert EnrichmentStatus.RUNNING.value == "running"
        assert EnrichmentStatus.FAILED.value == "failed"
        assert EnrichmentStatus.CANCELLED.value == "cancelled"
