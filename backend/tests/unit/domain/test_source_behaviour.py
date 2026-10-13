from __future__ import annotations

import pytest
from backend.domain.entities.source import Source
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit


def _content(source_format: Format, kind: Kind) -> Source:
    return Source(status=SourceStatus.NEW, format=source_format, kind=kind)


@pytest.mark.parametrize("source_format", [Format.VIDEO_FILE, Format.YOUTUBE])
def test_subtitles_of_a_video_have_a_video_and_keep_their_phrases(
    source_format: Format,
) -> None:
    source = _content(source_format, Kind.SUBTITLES)
    assert source.has_video
    assert not source.can_polish_phrases


@pytest.mark.parametrize(
    ("source_format", "kind"),
    [
        (Format.SRT, Kind.SUBTITLES),
        (Format.PLAIN, Kind.TEXT),
        (Format.EPUB, Kind.BOOK),
        (Format.MARKDOWN, Kind.SONG),
    ],
)
def test_content_without_a_video_can_polish_phrases(source_format: Format, kind: Kind) -> None:
    source = _content(source_format, kind)
    assert not source.has_video
    assert source.can_polish_phrases
    assert source.has_text
    assert not source.is_permanent


def test_topic_has_no_text_of_its_own() -> None:
    topic = Source(status=SourceStatus.NEW, role=SourceRole.TOPIC, topic_query="salary talks")
    assert not topic.has_text
    assert topic.can_polish_phrases
    assert not topic.is_permanent


def test_saved_phrases_source_has_no_text_and_is_permanent() -> None:
    source = Source.saved_phrases()

    assert source.role is SourceRole.SAVED_PHRASES
    assert source.status == SourceStatus.DONE
    assert not source.has_text
    assert source.is_permanent
    assert not source.can_polish_phrases
