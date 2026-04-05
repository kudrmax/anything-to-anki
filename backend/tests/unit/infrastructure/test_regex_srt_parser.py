import pytest
from backend.infrastructure.adapters.regex_srt_parser import RegexSrtParser


@pytest.mark.unit
class TestRegexSrtParser:
    def setup_method(self) -> None:
        self.parser = RegexSrtParser()

    def test_removes_block_numbers_and_timecodes(self) -> None:
        srt = "1\n00:00:01,000 --> 00:00:03,000\nHello world"
        result = self.parser.parse(srt)
        assert "-->" not in result
        assert result == "Hello world"

    def test_removes_positional_tags(self) -> None:
        srt = "1\n00:00:01,000 --> 00:00:03,000\n{\\an8}On screen text"
        result = self.parser.parse(srt)
        assert "{\\an8}" not in result
        assert "On screen text" in result

    def test_removes_html_tags_keeps_content(self) -> None:
        srt = "1\n00:00:01,000 --> 00:00:03,000\n<i>Italic text</i>"
        result = self.parser.parse(srt)
        assert "<i>" not in result
        assert "</i>" not in result
        assert "Italic text" in result

    def test_removes_sound_only_lines(self) -> None:
        srt = (
            "1\n00:00:01,000 --> 00:00:03,000\n(MUSIC PLAYING)\n\n"
            "2\n00:00:04,000 --> 00:00:06,000\n- (STICK TAPPING)\n\n"
            "3\n00:00:07,000 --> 00:00:09,000\n(CONNIE SIGHS)\n\n"
            "4\n00:00:10,000 --> 00:00:12,000\nHello"
        )
        result = self.parser.parse(srt)
        assert "(MUSIC PLAYING)" not in result
        assert "(STICK TAPPING)" not in result
        assert "(CONNIE SIGHS)" not in result
        assert "Hello" in result

    def test_removes_speaker_labels(self) -> None:
        srt = "1\n00:00:01,000 --> 00:00:03,000\nJOE: Hello there"
        result = self.parser.parse(srt)
        assert "JOE:" not in result
        assert "Hello there" in result

    def test_removes_credits_block_entirely(self) -> None:
        srt = (
            "1\n00:00:01,000 --> 00:00:03,000\nHello world\n\n"
            "2\n00:00:24,258 --> 00:00:29,258\nSubtitles by explosiveskull\n\n"
            "3\n00:00:30,000 --> 00:00:32,000\nGoodbye"
        )
        result = self.parser.parse(srt)
        assert "Subtitles by" not in result
        assert "explosiveskull" not in result
        assert "Hello world" in result
        assert "Goodbye" in result

    def test_preserves_dialogue(self) -> None:
        srt = (
            "1\n00:00:01,000 --> 00:00:03,000\nHow are you?\n\n"
            "2\n00:00:04,000 --> 00:00:06,000\nI'm fine, thanks."
        )
        result = self.parser.parse(srt)
        assert "How are you?" in result
        assert "I'm fine, thanks." in result

    def test_full_srt_with_multiple_blocks(self) -> None:
        srt = (
            "1\n00:00:01,335 --> 00:00:03,879\n(DISCORDANT JAZZ MUSIC PLAYING)\n\n"
            "2\n00:00:24,258 --> 00:00:29,258\nSubtitles by explosiveskull\n"
            "\U0001d544_\U0001d540_\U0001d542\U0001d53c\U0001d563\U0001d53c\U0001d53b\U0001d546\U0001d563\U0001d53c\U0001d563\U0001d563\n\n"
            "3\n00:00:32,741 --> 00:00:34,952\nJOE: <i>All right, let's try somethin' else.</i>\n\n"
            "4\n00:00:37,746 --> 00:00:42,334\n{\\an8}<i>Uh, from the top.\nReady. One, two, three.</i>"
        )
        result = self.parser.parse(srt)
        assert result == "All right, let's try somethin' else.\nUh, from the top.\nReady. One, two, three."

    def test_multiline_subtitle_block_preserved(self) -> None:
        srt = (
            "1\n00:00:01,000 --> 00:00:04,000\n"
            "First line of subtitle.\nSecond line of subtitle."
        )
        result = self.parser.parse(srt)
        assert "First line of subtitle." in result
        assert "Second line of subtitle." in result
        lines = result.splitlines()
        assert len(lines) == 2

    def test_empty_input(self) -> None:
        assert self.parser.parse("") == ""

    def test_only_sound_effects_returns_empty(self) -> None:
        srt = "1\n00:00:01,000 --> 00:00:03,000\n(AUDIENCE LAUGHING)"
        result = self.parser.parse(srt)
        assert result == ""
