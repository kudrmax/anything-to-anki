from __future__ import annotations

from backend.domain.ports.audio_track_lister import AudioTrackLister
from backend.domain.ports.subtitle_extractor import SubtitleExtractor
from backend.domain.ports.url_source_fetcher import UrlSourceFetcher
from backend.domain.value_objects.audio_track_info import AudioTrackInfo
from backend.domain.value_objects.fetched_subtitles import FetchedSubtitles
from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo

YOUTUBE_URL = "https://www.youtube.com/watch?v=abc"


def ass(*cues: tuple[int, str]) -> str:
    """ASS dialogue a second long each, starting at the given second."""
    header = (
        "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize\nStyle: Default,Arial,20\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    return header + "".join(
        f"Dialogue: 0,0:00:{start:02d}.00,0:00:{start + 1:02d}.00,Default,,0,0,0,,{text}\n"
        for start, text in cues
    )


def srt(*cues: tuple[int, str]) -> str:
    """Cues a second long each, starting at the given second."""
    return "\n\n".join(
        f"{n}\n00:00:{start:02d},000 --> 00:00:{start + 1:02d},000\n{text}"
        for n, (start, text) in enumerate(cues, 1)
    )


class FakeVideoTracks(SubtitleExtractor, AudioTrackLister):
    def __init__(
        self,
        subtitles: dict[int, str],
        audio_tracks: int = 1,
        codec: str = "subrip",
        fps: float | None = None,
    ) -> None:
        self._subtitles = subtitles
        self._audio_tracks = audio_tracks
        self._codec = codec
        self._fps = fps

    def list_tracks(self, video_path: str) -> list[SubtitleTrackInfo]:
        return [
            SubtitleTrackInfo(index=i, language="eng", title=f"Subs {i}", codec=self._codec)
            for i in self._subtitles
        ]

    def extract(self, video_path: str, track: SubtitleTrackInfo) -> str:
        return self._subtitles[track.index]

    def frame_rate(self, video_path: str) -> float | None:
        return self._fps

    def list_audio_tracks(self, video_path: str) -> list[AudioTrackInfo]:
        return [
            AudioTrackInfo(index=i, language=None, title=None, codec="aac", channels=2)
            for i in range(self._audio_tracks)
        ]


class FakeYouTube(UrlSourceFetcher):
    def __init__(self, srt_text: str = "") -> None:
        self._srt_text = srt_text

    def can_handle(self, url: str) -> bool:
        return "youtube.com" in url

    def fetch_subtitles(self, url: str, language: str = "en") -> FetchedSubtitles:
        return FetchedSubtitles(
            srt_text=self._srt_text, title="A talk",
        )
