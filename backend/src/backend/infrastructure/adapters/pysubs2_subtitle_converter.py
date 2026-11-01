from __future__ import annotations

import re

import pysubs2
from pysubs2.exceptions import FormatAutodetectionError, UnknownFPSError

SRT_FORMAT = "srt"
# The SRT that RegexSrtParser reads; pysubs2 calls looser text SRT too, YouTube's SBV among it.
_STRICT_SRT_TIMECODE_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->", re.MULTILINE)
# MicroDVD counts frames; a file that doesn't declare its frame rate and has no video
# to take it from is timed as a film, as ffmpeg and most players do.
FILM_FPS = 24000 / 1001


class Pysubs2SubtitleConverter:
    """Turns subtitles of any text format (ASS/SSA, WebVTT, MicroDVD, SAMI, TTML…) into SRT."""

    def to_srt(self, text: str, fps: float | None = None) -> str:
        """SRT and text in no subtitle format come back as they are.

        `fps` — the video's frame rate, for MicroDVD subtitles that don't declare their own.
        """
        if _STRICT_SRT_TIMECODE_RE.search(text):
            return text
        try:
            return self._subtitles(text, fps).to_string(SRT_FORMAT)
        except FormatAutodetectionError:
            return text

    def _subtitles(self, text: str, fps: float | None) -> pysubs2.SSAFile:
        try:
            return pysubs2.SSAFile.from_string(text)
        except UnknownFPSError:
            return pysubs2.SSAFile.from_string(text, fps=fps or FILM_FPS)
