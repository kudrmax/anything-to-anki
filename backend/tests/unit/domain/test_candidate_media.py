from __future__ import annotations

from datetime import UTC, datetime

import pytest
from backend.domain.entities.candidate_media import CandidateMedia


@pytest.mark.unit
class TestCandidateMedia:
    def test_construct_done(self) -> None:
        m = CandidateMedia(
            candidate_id=1,
            screenshot_path="/data/media/27/1_screenshot.webp",
            audio_path="/data/media/27/1_audio.m4a",
            start_ms=12000,
            end_ms=15000,
            generated_at=datetime(2026, 4, 7, tzinfo=UTC),
        )
        assert m.candidate_id == 1
        assert m.screenshot_path == "/data/media/27/1_screenshot.webp"
        assert m.audio_path == "/data/media/27/1_audio.m4a"
        assert m.start_ms == 12000
        assert m.end_ms == 15000

    def test_is_frozen(self) -> None:
        m = CandidateMedia(
            candidate_id=1, screenshot_path=None, audio_path=None,
            start_ms=None, end_ms=None, generated_at=None,
        )
        with pytest.raises((AttributeError, Exception)):
            m.start_ms = 5  # type: ignore[misc]
