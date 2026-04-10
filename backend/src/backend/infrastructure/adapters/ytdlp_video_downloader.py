from __future__ import annotations

import logging

from backend.domain.ports.video_downloader import VideoDownloader

logger = logging.getLogger(__name__)


class YtDlpVideoDownloader(VideoDownloader):
    """Downloads YouTube video using yt-dlp, capped at 1080p."""

    def download(self, url: str, output_path: str) -> None:
        import yt_dlp

        opts: dict = {
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        logger.info("Downloaded video %s → %s", url, output_path)
