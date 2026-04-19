from datetime import UTC, datetime

import dataclasses

from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


class TestCandidatePronunciation:
    def test_create_done(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=1,
            us_audio_path="/media/1/1_pron_us.mp3",
            uk_audio_path="/media/1/1_pron_uk.mp3",
            status=EnrichmentStatus.DONE,
            error=None,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert pron.candidate_id == 1
        assert pron.us_audio_path == "/media/1/1_pron_us.mp3"
        assert pron.uk_audio_path == "/media/1/1_pron_uk.mp3"
        assert pron.status == EnrichmentStatus.DONE

    def test_create_queued_no_paths(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=2,
            us_audio_path=None,
            uk_audio_path=None,
            status=EnrichmentStatus.QUEUED,
            error=None,
            generated_at=None,
        )
        assert pron.us_audio_path is None
        assert pron.uk_audio_path is None

    def test_frozen(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=1,
            us_audio_path=None,
            uk_audio_path=None,
            status=EnrichmentStatus.QUEUED,
            error=None,
            generated_at=None,
        )
        assert dataclasses.is_dataclass(pron)
        try:
            pron.status = EnrichmentStatus.DONE  # type: ignore[misc]
            assert False, "Should raise FrozenInstanceError"
        except dataclasses.FrozenInstanceError:
            pass
