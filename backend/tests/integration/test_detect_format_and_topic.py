from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.use_cases.create_topic import CreateTopicUseCase
from backend.application.use_cases.detect_format import DetectFormatUseCase
from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.source_input import LocalFile, PastedText, SourceInput, Url
from backend.domain.value_objects.source_role import SourceRole
from backend.infrastructure.adapters.regex_format_detector import RegexFormatDetector
from backend.infrastructure.persistence.sqla_source_repository import SqlaSourceRepository

from tests.unit.infrastructure.readers.fakes import YOUTUBE_URL, FakeYouTube

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("source_input", "expected"),
    [
        (LocalFile("/b/book.epub"), (Format.EPUB, "Book · epub")),
        (LocalFile("/v/movie.MKV"), (Format.VIDEO_FILE, "Video · mkv")),
        (LocalFile("/s/show.srt"), (Format.SRT, "Subtitles · srt")),
        (LocalFile("/n/notes.md"), (Format.MARKDOWN, "Text · markdown")),
        (LocalFile("/p/page.html"), (Format.HTML, "Text · html")),
        (LocalFile("'/t/my lyrics.txt'"), (Format.PLAIN, "Text · txt")),
        (LocalFile("/t/README"), (Format.PLAIN, "Text · txt")),
        (PastedText("# Title"), (Format.MARKDOWN, "Text · markdown")),
        (PastedText("Just text"), (Format.PLAIN, "Text")),
        (Url(YOUTUBE_URL), (Format.YOUTUBE, "Video · YouTube")),
        (Url("https://example.com/a"), (None, "Link not supported")),
    ],
)
def test_detected_format_and_its_label(
    source_input: SourceInput, expected: tuple[Format | None, str],
) -> None:
    detected = DetectFormatUseCase(RegexFormatDetector(FakeYouTube())).execute(source_input)
    assert (detected.format, detected.label) == expected


def test_topic_keeps_its_query(db_session: Session) -> None:
    topic = CreateTopicUseCase(SqlaSourceRepository(db_session)).execute("job interviews")

    assert topic.id is not None
    stored = SqlaSourceRepository(db_session).get_by_id(topic.id)
    assert stored is not None
    assert (stored.role, stored.topic_query, stored.title, stored.content_type) == (
        SourceRole.TOPIC, "job interviews", "job interviews", ContentType.TOPIC,
    )


def test_empty_topic(db_session: Session) -> None:
    with pytest.raises(InvalidSourceInputError):
        CreateTopicUseCase(SqlaSourceRepository(db_session)).execute("  ")
