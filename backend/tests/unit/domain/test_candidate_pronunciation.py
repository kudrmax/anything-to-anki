import dataclasses
from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation


class TestCandidatePronunciation:
    def test_create_done(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=1,
            us_audio_path="/media/1/1_pron_us.mp3",
            uk_audio_path="/media/1/1_pron_uk.mp3",
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert pron.candidate_id == 1
        assert pron.us_audio_path == "/media/1/1_pron_us.mp3"
        assert pron.uk_audio_path == "/media/1/1_pron_uk.mp3"

    def test_create_no_paths(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=2,
            us_audio_path=None,
            uk_audio_path=None,
            generated_at=None,
        )
        assert pron.us_audio_path is None
        assert pron.uk_audio_path is None

    def test_frozen(self) -> None:
        pron = CandidatePronunciation(
            candidate_id=1,
            us_audio_path=None,
            uk_audio_path=None,
            generated_at=None,
        )
        assert dataclasses.is_dataclass(pron)
        with pytest.raises(dataclasses.FrozenInstanceError):
            pron.us_audio_path = "/x"  # type: ignore[misc]
