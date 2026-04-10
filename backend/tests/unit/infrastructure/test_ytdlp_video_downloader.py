from backend.infrastructure.adapters.ytdlp_video_downloader import YtDlpVideoDownloader


class TestYtDlpVideoDownloaderInit:
    def test_can_instantiate(self) -> None:
        downloader = YtDlpVideoDownloader()
        assert downloader is not None
