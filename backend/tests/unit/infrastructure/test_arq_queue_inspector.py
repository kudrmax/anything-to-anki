"""Unit tests for parse_job_id function."""
from __future__ import annotations

import pytest

from backend.infrastructure.queue.arq_queue_inspector import parse_job_id


@pytest.mark.unit
class TestParseJobId:
    def test_meaning_job(self) -> None:
        result = parse_job_id("meaning_5_1720000000000_0001")
        assert result == ("meanings", 5, None)

    def test_media_job(self) -> None:
        result = parse_job_id("media_42_1720000000000")
        assert result == ("media", None, 42)

    def test_media_retry_job(self) -> None:
        result = parse_job_id("media_42_retry_1720000000000")
        assert result == ("media", None, 42)

    def test_pronunciation_job(self) -> None:
        result = parse_job_id("pronunciation_42_1720000000000")
        assert result == ("pronunciation", None, 42)

    def test_youtube_job(self) -> None:
        result = parse_job_id("youtube_5_1720000000000")
        assert result == ("youtube_dl", 5, None)

    def test_unknown_format_returns_none(self) -> None:
        result = parse_job_id("something_weird")
        assert result is None
