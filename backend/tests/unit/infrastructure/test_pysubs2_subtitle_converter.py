from __future__ import annotations

import pytest
from backend.infrastructure.adapters.pysubs2_subtitle_converter import Pysubs2SubtitleConverter

CONVERTER = Pysubs2SubtitleConverter()

ASS_HEADER = (
    "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize\nStyle: Default,Arial,20\n\n[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)


@pytest.mark.unit
class TestPysubs2SubtitleConverter:
    def test_srt_stays_as_it_is(self) -> None:
        srt = "1\n00:00:01,000 --> 00:00:02,000\n<i>Hi</i> {\\an8}there\n"
        assert CONVERTER.to_srt(srt) == srt

    def test_ass_dialogue_becomes_srt_without_comments_and_drawings(self) -> None:
        ass = ASS_HEADER + (
            "Comment: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,A translator's note\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Signs,,0,0,0,,{\\p1}m 0 0 l 100 0 100 100{\\p0}\n"
            "Dialogue: 0,0:00:03.00,0:00:04.50,Default,,0,0,0,,{\\i1}Oh{\\i0}, my god.\\NThink.\n"
        )
        assert CONVERTER.to_srt(ass) == (
            "1\n00:00:03,000 --> 00:00:04,500\n<i>Oh</i>, my god.\nThink.\n\n"
        )

    def test_webvtt_becomes_srt(self) -> None:
        vtt = (
            "WEBVTT\n\nNOTE a comment\n\n"
            "00:00:01.000 --> 00:00:02.500 align:start\n<v Bob>Hello there\n\n"
            "00:03.000 --> 00:04.000\nSecond\n"
        )
        assert CONVERTER.to_srt(vtt) == (
            "1\n00:00:01,000 --> 00:00:02,500\nHello there\n\n"
            "2\n00:00:03,000 --> 00:00:04,000\nSecond\n\n"
        )

    def test_microdvd_takes_the_frame_rate_it_declares(self) -> None:
        microdvd = "{1}{1}25.000\n{25}{50}Hello|world\n"
        assert CONVERTER.to_srt(microdvd, fps=50) == (
            "1\n00:00:01,000 --> 00:00:02,000\nHello\nworld\n\n"
        )

    def test_microdvd_without_a_frame_rate_takes_the_video_one(self) -> None:
        assert CONVERTER.to_srt("{25}{50}Hello\n", fps=25) == (
            "1\n00:00:01,000 --> 00:00:02,000\nHello\n\n"
        )

    def test_microdvd_without_any_frame_rate_takes_the_film_one(self) -> None:
        assert CONVERTER.to_srt("{24}{48}Hello\n") == (
            "1\n00:00:01,001 --> 00:00:02,002\nHello\n\n"
        )

    @pytest.mark.parametrize(
        "text",
        [
            "<SAMI><BODY>\n<SYNC Start=1000><P>Hello\n"
            "<SYNC Start=2000><P>&nbsp;\n</BODY></SAMI>\n",
            '<tt xmlns="http://www.w3.org/ns/ttml"><body><div>'
            '<p begin="00:00:01.000" end="00:00:02.000">Hello</p></div></body></tt>\n',
            "0:00:01.000,0:00:02.000\nHello\n",
        ],
        ids=["sami", "ttml", "sbv"],
    )
    def test_other_text_formats_become_srt(self, text: str) -> None:
        assert CONVERTER.to_srt(text).startswith("1\n00:00:01,000 --> 00:00:0")
        assert "\nHello\n" in CONVERTER.to_srt(text)

    def test_text_in_no_subtitle_format_stays_as_it_is(self) -> None:
        assert CONVERTER.to_srt("Just some words.") == "Just some words."
