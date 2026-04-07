from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


@pytest.mark.unit
class TestCandidateMeaning:
    def test_construct_done(self) -> None:
        m = CandidateMeaning(
            candidate_id=1,
            meaning="выгорание",
            ipa="ˈbɜːnaʊt",
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime(2026, 4, 7, tzinfo=UTC),
        )
        assert m.candidate_id == 1
        assert m.meaning == "выгорание"
        assert m.ipa == "ˈbɜːnaʊt"
        assert m.status == EnrichmentStatus.DONE
        assert m.error is None

    def test_is_frozen(self) -> None:
        m = CandidateMeaning(
            candidate_id=1,
            meaning="x",
            ipa=None,
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=None,
        )
        with pytest.raises((AttributeError, Exception)):
            m.meaning = "y"  # type: ignore[misc]

    def test_failed_state(self) -> None:
        m = CandidateMeaning(
            candidate_id=2,
            meaning=None,
            ipa=None,
            status=EnrichmentStatus.FAILED,
            error="rate limited",
            generated_at=None,
        )
        assert m.status == EnrichmentStatus.FAILED
        assert m.error == "rate limited"
