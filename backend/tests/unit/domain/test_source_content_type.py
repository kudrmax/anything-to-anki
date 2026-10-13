from __future__ import annotations

import pytest
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType, resolve_content_type
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit


def test_topic_query_is_a_topic() -> None:
    assert resolve_content_type(InputMethod.TOPIC_QUERY) == ContentType.TOPIC


def test_phrase_added_goes_to_phrases() -> None:
    assert resolve_content_type(InputMethod.PHRASE_ADDED) == ContentType.PHRASES


def test_saved_phrases_source_has_no_text_and_is_permanent() -> None:
    source = Source.saved_phrases()

    assert source.content_type == ContentType.PHRASES
    assert source.role is SourceRole.SAVED_PHRASES
    assert source.status == SourceStatus.DONE
    assert not source.has_text
    assert source.is_permanent
    assert not source.can_polish_phrases
