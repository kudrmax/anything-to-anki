from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.domain.exceptions import InvalidSourceInputError, UnsupportedUrlError
from backend.domain.value_objects.content import LocalVideo, SubtitlesContent, YouTubeVideo
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_input import LocalFile, PastedText, Url
from backend.infrastructure.adapters.local_file_reader import LocalFileReader
from backend.infrastructure.readers.srt_reader import SrtReader
from backend.infrastructure.readers.video_file_reader import (
    AUDIO_TRACK_QUESTION_ID,
    SUBTITLE_TRACK_QUESTION_ID,
    VideoFileReader,
)
from backend.infrastructure.readers.youtube_reader import YouTubeReader

from tests.unit.infrastructure.readers.fakes import YOUTUBE_URL, FakeVideoTracks, FakeYouTube, srt

if TYPE_CHECKING:
    from pathlib import Path

FILES = LocalFileReader()
NO_ANSWERS = Answers()


def subtitles(*lines: Line) -> Document:
    return Document((Paragraph(lines=lines, mode=ParagraphMode.FLOW),))


@pytest.mark.unit
class TestSrtReader:
    def test_lines_of_a_subtitle_keep_its_time(self) -> None:
        text = srt((1, "I told him"), (3, "[sighs]\nthat we were\nbewildered."))
        content = SrtReader(FILES).read(PastedText(text), NO_ANSWERS)
        assert content == SubtitlesContent(
            title=None,
            document=subtitles(
                Line("I told him", 1000, 2000),
                Line("that we were", 3000, 4000),
                Line("bewildered.", 3000, 4000),
            ),
        )

    def test_drops_rolling_repeats_of_auto_captions(self) -> None:
        text = srt((1, "so I went"), (2, "so I went\nto the store"), (3, "to the store\nand"))
        content = SrtReader(FILES).read(PastedText(text), NO_ANSWERS)
        assert [line.text for line in content.document.blocks[0].lines] == [  # type: ignore[union-attr]
            "so I went", "to the store", "and",
        ]

    def test_subtitles_with_nothing_to_read_are_an_error(self) -> None:
        with pytest.raises(InvalidSourceInputError):
            SrtReader(FILES).read(PastedText(srt((1, "[music]"))), NO_ANSWERS)


@pytest.mark.unit
class TestVideoFileReader:
    def test_one_track_of_each_needs_no_questions(self, tmp_path: Path) -> None:
        reader = VideoFileReader(FILES, tracks := FakeVideoTracks({3: srt((1, "Hi"))}), tracks)
        video = LocalFile(str(tmp_path / "Movie.mkv"))
        assert reader.questions(video) == ()
        content = reader.read(video, NO_ANSWERS)
        assert content == SubtitlesContent(
            title="Movie.mkv",
            document=subtitles(Line("Hi", 1000, 2000)),
            video=LocalVideo(path=video.path, audio_track=None),
        )

    def test_asks_for_tracks_when_there_are_several(self) -> None:
        tracks = FakeVideoTracks({2: srt((1, "Two")), 5: srt((1, "Five"))}, audio_tracks=2)
        reader = VideoFileReader(FILES, tracks, tracks)
        video = LocalFile("/v/movie.mkv")

        subtitle_question, audio_question = reader.questions(video)
        assert (subtitle_question.id, subtitle_question.option_ids) == (
            SUBTITLE_TRACK_QUESTION_ID, ("2", "5"),
        )
        assert subtitle_question.options[0].label == "Subs 2 — eng · subrip"
        assert audio_question.options[1].label == "Track 1 — — · aac · 2ch"

        answers = Answers({SUBTITLE_TRACK_QUESTION_ID: "5", AUDIO_TRACK_QUESTION_ID: "1"})
        content = reader.read(video, answers)
        assert content.document == subtitles(Line("Five", 1000, 2000))  # type: ignore[union-attr]
        assert content.video == LocalVideo(path=video.path, audio_track=1)  # type: ignore[union-attr]

    def test_attached_srt_wins_over_the_tracks(self, tmp_path: Path) -> None:
        attached = tmp_path / "movie.srt"
        attached.write_text(srt((1, "Attached")))
        tracks = FakeVideoTracks({1: srt((1, "One")), 2: srt((1, "Two"))})
        reader = VideoFileReader(FILES, tracks, tracks)
        video = LocalFile("/v/movie.mkv", subtitles_path=str(attached))
        assert reader.questions(video) == ()
        content = reader.read(video, NO_ANSWERS)
        assert content.document == subtitles(Line("Attached", 1000, 2000))  # type: ignore[union-attr]

    def test_video_without_subtitles_asks_for_an_srt(self) -> None:
        tracks = FakeVideoTracks({})
        with pytest.raises(InvalidSourceInputError, match="attach a .srt"):
            VideoFileReader(FILES, tracks, tracks).questions(LocalFile("/v/movie.mkv"))


@pytest.mark.unit
class TestYouTubeReader:
    def test_subtitles_now_video_later(self) -> None:
        reader = YouTubeReader(FakeYouTube(srt((1, "Welcome"))))
        content = reader.read(Url(YOUTUBE_URL), NO_ANSWERS)
        assert content == SubtitlesContent(
            title="A talk",
            document=subtitles(Line("Welcome", 1000, 2000)),
            video=YouTubeVideo(url=YOUTUBE_URL),
        )

    def test_other_links_are_not_supported(self) -> None:
        with pytest.raises(UnsupportedUrlError):
            YouTubeReader(FakeYouTube()).read(Url("https://vimeo.com/1"), NO_ANSWERS)
