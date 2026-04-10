from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from backend.domain.exceptions import SubtitlesNotAvailableError
from backend.domain.ports.url_source_fetcher import UrlSourceFetcher
from backend.domain.value_objects.fetched_subtitles import FetchedSubtitles
from backend.domain.value_objects.input_method import InputMethod

logger = logging.getLogger(__name__)

_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}


class YtDlpSubtitleFetcher(UrlSourceFetcher):
    """Fetches English subtitles from YouTube using yt-dlp."""

    def can_handle(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.hostname in _YOUTUBE_HOSTS if parsed.hostname else False
        except Exception:
            return False

    def fetch_subtitles(self, url: str, language: str = "en") -> FetchedSubtitles:
        import yt_dlp

        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = str(Path(tmpdir) / "sub")
            opts: dict = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [language],
                "subtitlesformat": "srt",
                "skip_download": True,
                "outtmpl": outtmpl,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

            if info is None:
                raise SubtitlesNotAvailableError(
                    "Субтитры для видео не получилось получить"
                )

            title = info.get("title", url)

            srt_path = Path(tmpdir) / f"sub.{language}.srt"
            if not srt_path.exists():
                candidates = list(Path(tmpdir).glob("sub.*.srt"))
                if candidates:
                    srt_path = candidates[0]
                else:
                    raise SubtitlesNotAvailableError(
                        "Субтитры для видео не получилось получить"
                    )

            srt_text = srt_path.read_text(encoding="utf-8", errors="replace")
            if not srt_text.strip():
                raise SubtitlesNotAvailableError(
                    "Субтитры для видео не получилось получить"
                )

            logger.info(
                "Fetched subtitles for %s: %d chars, title=%r",
                url, len(srt_text), title,
            )
            return FetchedSubtitles(
                srt_text=srt_text,
                title=str(title),
                input_method=InputMethod.YOUTUBE_URL,
            )
