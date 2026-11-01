"""Subtitle tracks of a real video, read by the real ffmpeg: ASS stays ASS, so its drawings and
comments never become words."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_input import LocalFile
from backend.infrastructure.adapters.ffmpeg_subtitle_extractor import FfmpegSubtitleExtractor
from backend.infrastructure.adapters.local_file_reader import LocalFileReader
from backend.infrastructure.readers.video_file_reader import (
    SUBTITLE_TRACK_QUESTION_ID,
    VideoFileReader,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed"),
]

_FPS = 10
_ASS = (
    "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
    "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,"
    "1,2,2,2,10,10,10,1\n\n[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    "Comment: 0,0:00:00.20,0:00:00.80,Default,,0,0,0,,A translator's note\n"
    "Dialogue: 0,0:00:00.20,0:00:00.80,Default,,0,0,0,,{\\p1}m 0 0 l 100 0 100 100{\\p0}\n"
    "Dialogue: 0,0:00:01.00,0:00:01.50,Default,,0,0,0,,{\\i1}Oh{\\i0}, my god.\n"
)
_SRT = "1\n00:00:01,000 --> 00:00:01,500\nThink, think.\n"


@pytest.fixture
def video(tmp_path: Path) -> Path:
    (tmp_path / "eng.ass").write_text(_ASS)
    (tmp_path / "eng.srt").write_text(_SRT)
    path = tmp_path / "movie.mkv"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"testsrc=size=160x120:duration=2:rate={_FPS}",
            "-i", str(tmp_path / "eng.ass"),
            "-i", str(tmp_path / "eng.srt"),
            "-map", "0", "-map", "1", "-map", "2",
            "-c:v", "mpeg4", "-c:s", "copy",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return path


def _read(video: Path, track: str) -> Document:
    extractor = FfmpegSubtitleExtractor()
    reader = VideoFileReader(LocalFileReader(), extractor, extractor)
    content = reader.read(LocalFile(str(video)), Answers({SUBTITLE_TRACK_QUESTION_ID: track}))
    return content.document  # type: ignore[attr-defined, no-any-return]


def _subtitles(*lines: Line) -> Document:
    return Document((Paragraph(lines=lines, mode=ParagraphMode.FLOW),))


def test_lists_the_tracks_with_their_codecs(video: Path) -> None:
    tracks = FfmpegSubtitleExtractor().list_tracks(str(video))
    assert [(track.index, track.codec) for track in tracks] == [(0, "ass"), (1, "subrip")]


def test_ass_track_keeps_only_its_dialogue(video: Path) -> None:
    assert _read(video, "0") == _subtitles(Line("Oh, my god.", 1000, 1500))


def test_srt_track(video: Path) -> None:
    assert _read(video, "1") == _subtitles(Line("Think, think.", 1000, 1500))


def test_frame_rate(video: Path) -> None:
    assert FfmpegSubtitleExtractor().frame_rate(str(video)) == _FPS


def test_picture_tracks_are_left_out_but_keep_the_numbering() -> None:
    probed = {"streams": [
        {"codec_name": "hdmv_pgs_subtitle", "tags": {"language": "rus"}},
        {"codec_name": "ass", "tags": {"language": "eng"}},
        {"codec_name": "dvd_subtitle"},
    ]}
    result = MagicMock(returncode=0, stdout=json.dumps(probed))
    with patch("subprocess.run", return_value=result):
        tracks = FfmpegSubtitleExtractor().list_tracks("/v/movie.mkv")
    assert [(track.index, track.codec) for track in tracks] == [(1, "ass")]
