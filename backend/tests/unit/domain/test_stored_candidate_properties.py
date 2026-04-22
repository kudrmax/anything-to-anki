from __future__ import annotations

import pytest
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.frequency_band import FrequencyBand


def _make(zipf: float) -> StoredCandidate:
    return StoredCandidate(
        source_id=1,
        lemma="test",
        pos="NN",
        cefr_level="B1",
        zipf_frequency=zipf,
        context_fragment="test context",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.PENDING,
    )


@pytest.mark.unit
class TestStoredCandidateProperties:
    def test_frequency_band_mid(self) -> None:
        c = _make(4.0)
        assert c.frequency_band == FrequencyBand.MID

    def test_frequency_band_rare(self) -> None:
        c = _make(1.5)
        assert c.frequency_band == FrequencyBand.RARE

    def test_frequency_band_ultra_common(self) -> None:
        c = _make(6.0)
        assert c.frequency_band == FrequencyBand.ULTRA_COMMON

    def test_is_sweet_spot_true_for_mid(self) -> None:
        c = _make(4.0)  # MID band
        assert c.is_sweet_spot is True

    def test_is_sweet_spot_false_for_other_bands(self) -> None:
        assert _make(5.5).is_sweet_spot is False  # ULTRA_COMMON
        assert _make(5.0).is_sweet_spot is False  # COMMON
        assert _make(3.0).is_sweet_spot is False  # LOW
        assert _make(1.0).is_sweet_spot is False  # RARE

    def test_frequency_band_changes_with_zipf(self) -> None:
        """frequency_band is always computed from current zipf_frequency."""
        c = _make(4.0)
        assert c.frequency_band == FrequencyBand.MID
        c.zipf_frequency = 6.0
        assert c.frequency_band == FrequencyBand.ULTRA_COMMON
