from __future__ import annotations

import pytest
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType, resolve_content_type
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit


def _source(input_method: InputMethod, cleaned_text: str | None = None) -> Source:
    return Source(
        raw_text="raw text",
        status=SourceStatus.NEW,
        input_method=input_method,
        content_type=resolve_content_type(input_method),
        cleaned_text=cleaned_text,
    )


def test_topic_query_is_a_topic() -> None:
    assert resolve_content_type(InputMethod.TOPIC_QUERY) == ContentType.TOPIC


def test_cleaned_text_is_searchable() -> None:
    assert _source(InputMethod.SUBTITLES_FILE, "clean text").searchable_text == "clean text"


def test_unprocessed_plain_text_is_searchable() -> None:
    assert _source(InputMethod.TEXT_PASTED).searchable_text == "raw text"


def test_unprocessed_subtitles_are_not_searchable() -> None:
    assert _source(InputMethod.SUBTITLES_FILE).searchable_text is None


def test_topic_is_never_searchable() -> None:
    assert _source(InputMethod.TOPIC_QUERY, "phrases of the topic").searchable_text is None
