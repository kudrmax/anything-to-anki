from __future__ import annotations

import json
import os
import subprocess
import tempfile

from backend.domain.ports.audio_track_lister import AudioTrackLister
from backend.domain.ports.subtitle_extractor import SubtitleExtractor
from backend.domain.value_objects.audio_track_info import AudioTrackInfo
from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


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
        for stream in data.get("streams", []):
            tags = stream.get("tags", {})
            sub_index = len(tracks)  # subtitle stream index (not global stream index)
            tracks.append(SubtitleTrackInfo(
                index=sub_index,
                language=tags.get("language"),
                title=tags.get("title"),
                codec=stream.get("codec_name", "unknown"),
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

    def extract(self, video_path: str, track_index: int) -> str:
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-map", f"0:s:{track_index}",
                    "-f", "srt",
                    tmp_path,
                ],
                capture_output=True,
                check=True,
            )
            with open(tmp_path, encoding="utf-8", errors="replace") as f:
                return f.read()
        finally:
            os.unlink(tmp_path)
