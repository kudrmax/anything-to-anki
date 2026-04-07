import pytest
from backend.application.utils.timecode_mapping import find_timecodes
from backend.domain.value_objects.subtitle_block import SubtitleBlock
from backend.domain.value_objects.parsed_srt import ParsedSrt


def _make_parsed_srt() -> ParsedSrt:
    # "I think you should\ngo back to school.\nHello world."
    #  0                  19                  38
    text = "I think you should\ngo back to school.\nHello world."
    blocks = (
        SubtitleBlock(start_ms=1200, end_ms=2500, char_start=0, char_end=19),
        SubtitleBlock(start_ms=2500, end_ms=4000, char_start=19, char_end=38),
        SubtitleBlock(start_ms=4000, end_ms=5000, char_start=38, char_end=50),
    )
    return ParsedSrt(text=text, blocks=blocks)


@pytest.mark.unit
class TestFindTimecodes:
    def test_fragment_within_single_block(self) -> None:
        parsed = _make_parsed_srt()
        result = find_timecodes("Hello world.", parsed)
        assert result == (4000, 5000)

    def test_fragment_spanning_two_blocks(self) -> None:
        parsed = _make_parsed_srt()
        result = find_timecodes("you should\ngo back", parsed)
        assert result == (1200, 4000)

    def test_fragment_not_found_returns_none(self) -> None:
        parsed = _make_parsed_srt()
        result = find_timecodes("something not in text", parsed)
        assert result is None

    def test_empty_blocks_returns_none(self) -> None:
        parsed = ParsedSrt(text="hello world", blocks=())
        result = find_timecodes("hello", parsed)
        assert result is None
