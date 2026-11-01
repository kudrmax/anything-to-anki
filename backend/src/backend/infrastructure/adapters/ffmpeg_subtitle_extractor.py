from __future__ import annotations

import json
import subprocess
from fractions import Fraction

from backend.domain.ports.audio_track_lister import AudioTrackLister
from backend.domain.ports.subtitle_extractor import SubtitleExtractor
from backend.domain.value_objects.audio_track_info import AudioTrackInfo
from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo

# Subtitles drawn as pictures: there is no text to take from them.
PICTURE_SUBTITLE_CODECS = frozenset({
    "hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub",
})
# Taken as they are: ffmpeg's SRT would keep their drawings and signs as text.
ASS_CODECS = frozenset({"ass", "ssa"})
ASS_FORMAT = "ass"
SRT_FORMAT = "srt"


class FfmpegSubtitleExtractor(SubtitleExtractor, AudioTrackLister):
    """Extracts subtitle tracks and lists audio tracks from video files via ffprobe/ffmpeg."""

    def list_tracks(self, video_path: str) -> list[SubtitleTrackInfo]:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "s",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []

        data = json.loads(result.stdout or "{}")
        tracks: list[SubtitleTrackInfo] = []
        # subtitle stream index (not global stream index), counting the picture ones too
        for sub_index, stream in enumerate(data.get("streams", [])):
            codec = stream.get("codec_name", "unknown")
            if codec in PICTURE_SUBTITLE_CODECS:
                continue
            tags = stream.get("tags", {})
            tracks.append(SubtitleTrackInfo(
                index=sub_index,
                language=tags.get("language"),
                title=tags.get("title"),
                codec=codec,
            ))
        return tracks

    def list_audio_tracks(self, video_path: str) -> list[AudioTrackInfo]:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "a",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []

        data = json.loads(result.stdout or "{}")
        tracks: list[AudioTrackInfo] = []
        for stream in data.get("streams", []):
            tags = stream.get("tags", {})
            audio_index = len(tracks)  # audio stream index (not global stream index)
            channels_raw = stream.get("channels")
            channels: int | None = int(channels_raw) if channels_raw is not None else None
            tracks.append(AudioTrackInfo(
                index=audio_index,
                language=tags.get("language"),
                title=tags.get("title"),
                codec=stream.get("codec_name", "unknown"),
                channels=channels,
            ))
        return tracks

    def extract(self, video_path: str, track: SubtitleTrackInfo) -> str:
        output_format = ASS_FORMAT if track.codec in ASS_CODECS else SRT_FORMAT
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error",
                "-i", video_path,
                "-map", f"0:s:{track.index}",
                "-f", output_format,
                "-",
            ],
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8", errors="replace")

    def frame_rate(self, video_path: str) -> float | None:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_entries", "stream=r_frame_rate",
                "-select_streams", "v:0",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        streams = json.loads(result.stdout or "{}").get("streams", [])
        rate = streams[0].get("r_frame_rate", "0/0") if streams else "0/0"
        numerator, _, denominator = rate.partition("/")
        if not numerator.isdigit() or not denominator.isdigit() or int(denominator) == 0:
            return None
        return float(Fraction(int(numerator), int(denominator))) or None
