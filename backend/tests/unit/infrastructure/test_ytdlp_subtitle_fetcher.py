from backend.infrastructure.adapters.ytdlp_subtitle_fetcher import YtDlpSubtitleFetcher


class TestYtDlpSubtitleFetcherCanHandle:
    def setup_method(self) -> None:
        self.fetcher = YtDlpSubtitleFetcher()

    def test_youtube_com_url(self) -> None:
        assert self.fetcher.can_handle("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_youtu_be_short_url(self) -> None:
        assert self.fetcher.can_handle("https://youtu.be/dQw4w9WgXcQ")

    def test_youtube_with_playlist(self) -> None:
        assert self.fetcher.can_handle("https://www.youtube.com/watch?v=abc&list=xyz")

    def test_non_youtube_url(self) -> None:
        assert not self.fetcher.can_handle("https://genius.com/some-lyrics")

    def test_random_url(self) -> None:
        assert not self.fetcher.can_handle("https://example.com")

    def test_empty_string(self) -> None:
        assert not self.fetcher.can_handle("")
