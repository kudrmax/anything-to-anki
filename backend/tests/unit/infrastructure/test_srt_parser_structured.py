import pytest
from backend.infrastructure.adapters.regex_srt_parser import RegexSrtParser

SRT_SIMPLE = """\
1
00:00:01,200 --> 00:00:02,500
I think you should

2
00:00:02,500 --> 00:00:04,000
go back to school.

3
00:00:04,500 --> 00:00:05,000
(APPLAUSE)

4
00:00:05,500 --> 00:00:07,000
Hello world.
"""

SRT_WITH_CREDITS = """\
1
00:00:01,000 --> 00:00:02,000
Hello there.

2
00:00:02,000 --> 00:00:03,000
Subtitles by OpenSubtitles
"""

SRT_HTML_TAGS = """\
1
00:00:01,000 --> 00:00:02,500
<i>What a <b>wonderful</b> day.</i>
"""


@pytest.mark.unit
class TestRegexSrtParserStructured:
    def setup_method(self) -> None:
        self.parser = RegexSrtParser()

    def test_char_offsets_match_text(self) -> None:
        result = self.parser.parse_structured(SRT_SIMPLE)
        texts = [result.text[b.char_start:b.char_end].strip() for b in result.blocks]
        assert texts[0] == "I think you should"
        assert texts[1] == "go back to school."
        assert texts[2] == "Hello world."

    def test_char_end_within_text_bounds(self) -> None:
        result = self.parser.parse_structured(SRT_SIMPLE)
        for block in result.blocks:
            assert block.char_end <= len(result.text), (
                f"char_end={block.char_end} exceeds text length={len(result.text)}"
            )

    def test_timecodes_parsed_correctly(self) -> None:
        result = self.parser.parse_structured(SRT_SIMPLE)
        assert result.blocks[0].start_ms == 1200
        assert result.blocks[0].end_ms == 2500
        assert result.blocks[1].start_ms == 2500
        assert result.blocks[1].end_ms == 4000

    def test_skips_sound_description_block(self) -> None:
        result = self.parser.parse_structured(SRT_SIMPLE)
        # Block 3 "(APPLAUSE)" should be cleaned out — no SubtitleBlock for it
        texts = [result.text[b.char_start:b.char_end].strip() for b in result.blocks]
        assert all("APPLAUSE" not in t for t in texts)
        # Only 3 blocks: 2 text + 1 more after applause
        assert len(result.blocks) == 3

    def test_credits_block_skipped(self) -> None:
        result = self.parser.parse_structured(SRT_WITH_CREDITS)
        assert len(result.blocks) == 1
        assert result.blocks[0].start_ms == 1000

    def test_html_tags_stripped(self) -> None:
        result = self.parser.parse_structured(SRT_HTML_TAGS)
        assert "<i>" not in result.text
        assert "<b>" not in result.text
        assert "wonderful" in result.text

    def test_parse_returns_same_text(self) -> None:
        """parse() must return the same text as parse_structured().text"""
        plain = self.parser.parse(SRT_SIMPLE)
        structured = self.parser.parse_structured(SRT_SIMPLE)
        assert plain == structured.text

    def test_blocks_non_overlapping_ordered(self) -> None:
        result = self.parser.parse_structured(SRT_SIMPLE)
        for i in range(len(result.blocks) - 1):
            assert result.blocks[i].char_end <= result.blocks[i + 1].char_start
