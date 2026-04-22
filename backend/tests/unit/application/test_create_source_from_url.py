from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.create_source_from_url import CreateSourceFromUrlUseCase
from backend.domain.exceptions import SubtitlesNotAvailableError, UnsupportedUrlError
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.fetched_subtitles import FetchedSubtitles
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


class TestCreateSourceFromUrl:
    def setup_method(self) -> None:
        self.source_repo = MagicMock()
        self.source_repo.create.side_effect = lambda s: s
        self.fetcher = MagicMock()
        self.fetcher.can_handle.return_value = True
        self.fetcher.fetch_subtitles.return_value = FetchedSubtitles(
            srt_text="1\n00:00:01,000 --> 00:00:02,000\nHello world\n",
            title="Test Video",
            input_method=InputMethod.YOUTUBE_URL,
        )
        self.use_case = CreateSourceFromUrlUseCase(
            source_repo=self.source_repo,
            fetchers=[self.fetcher],
        )

    def test_creates_source_with_correct_fields(self) -> None:
        source = self.use_case.execute("https://youtube.com/watch?v=abc")
        assert source.input_method == InputMethod.YOUTUBE_URL
        assert source.content_type == ContentType.VIDEO
        assert source.source_url == "https://youtube.com/watch?v=abc"
        assert source.title == "Test Video"
        assert source.status == SourceStatus.NEW

    def test_title_override(self) -> None:
        source = self.use_case.execute("https://youtube.com/watch?v=abc", title_override="My Title")
        assert source.title == "My Title"

    def test_unsupported_url_raises(self) -> None:
        self.fetcher.can_handle.return_value = False
        with pytest.raises(UnsupportedUrlError):
            self.use_case.execute("https://example.com/foo")

    def test_no_subtitles_propagates_error(self) -> None:
        self.fetcher.fetch_subtitles.side_effect = SubtitlesNotAvailableError("no subs")
        with pytest.raises(SubtitlesNotAvailableError):
            self.use_case.execute("https://youtube.com/watch?v=abc")
