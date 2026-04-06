import pytest
from backend.domain.value_objects.subtitle_block import SubtitleBlock
from backend.domain.value_objects.parsed_srt import ParsedSrt
from backend.domain.value_objects.subtitle_track_info import SubtitleTrackInfo


@pytest.mark.unit
class TestSubtitleBlock:
    def test_is_frozen(self) -> None:
        block = SubtitleBlock(start_ms=1000, end_ms=2000, char_start=0, char_end=10)
        with pytest.raises(Exception):
            block.start_ms = 999  # type: ignore[misc]

    def test_fields(self) -> None:
        block = SubtitleBlock(start_ms=1200, end_ms=2500, char_start=5, char_end=25)
        assert block.start_ms == 1200
        assert block.end_ms == 2500
        assert block.char_start == 5
        assert block.char_end == 25


@pytest.mark.unit
class TestParsedSrt:
    def test_is_frozen(self) -> None:
        p = ParsedSrt(text="hello", blocks=[])
        with pytest.raises(Exception):
            p.text = "bye"  # type: ignore[misc]

    def test_fields(self) -> None:
        block = SubtitleBlock(start_ms=0, end_ms=1000, char_start=0, char_end=5)
        p = ParsedSrt(text="hello", blocks=[block])
        assert p.text == "hello"
        assert len(p.blocks) == 1


@pytest.mark.unit
class TestSubtitleTrackInfo:
    def test_fields(self) -> None:
        t = SubtitleTrackInfo(index=0, language="eng", title="English", codec="subrip")
        assert t.index == 0
        assert t.language == "eng"
        assert t.codec == "subrip"
