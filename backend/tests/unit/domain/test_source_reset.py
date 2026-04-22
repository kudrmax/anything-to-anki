from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest
from backend.domain.entities.source import (
    _SOURCE_DERIVED_FIELDS,
    _SOURCE_INPUT_FIELDS,
    Source,
)
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


def _make_source(**kwargs: object) -> Source:
    defaults: dict[str, object] = {
        "id": 42,
        "raw_text": "Hello world",
        "title": "My source",
        "input_method": InputMethod.TEXT_PASTED,
        "content_type": ContentType.TEXT,
        "source_url": "https://example.com",
        "video_path": "/tmp/video.mp4",
        "audio_track_index": 1,
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "status": SourceStatus.DONE,
        "cleaned_text": "Hello world cleaned",
        "error_message": "some error",
        "processing_stage": None,
    }
    defaults.update(kwargs)
    return Source(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestSourceFieldClassification:
    def test_all_fields_classified(self) -> None:
        all_fields = {f.name for f in dataclasses.fields(Source)}
        classified = _SOURCE_INPUT_FIELDS | _SOURCE_DERIVED_FIELDS
        assert classified == all_fields, (
            f"Unclassified fields: {all_fields - classified}; "
            f"Extra fields: {classified - all_fields}"
        )

    def test_no_overlap(self) -> None:
        overlap = _SOURCE_INPUT_FIELDS & _SOURCE_DERIVED_FIELDS
        assert overlap == frozenset(), f"Fields in both sets: {overlap}"


@pytest.mark.unit
class TestSourceResetToInitialState:
    def test_preserves_input_fields(self) -> None:
        created_at = datetime(2024, 6, 15, tzinfo=UTC)
        source = _make_source(created_at=created_at)
        reset = source.reset_to_initial_state()

        assert reset.id == 42
        assert reset.raw_text == "Hello world"
        assert reset.title == "My source"
        assert reset.input_method == InputMethod.TEXT_PASTED
        assert reset.content_type == ContentType.TEXT
        assert reset.source_url == "https://example.com"
        assert reset.video_path == "/tmp/video.mp4"
        assert reset.audio_track_index == 1
        assert reset.created_at == created_at

    def test_resets_derived_fields(self) -> None:
        source = _make_source(
            status=SourceStatus.DONE,
            cleaned_text="cleaned",
            error_message="oops",
            processing_stage=None,
        )
        reset = source.reset_to_initial_state()

        assert reset.status == SourceStatus.NEW
        assert reset.cleaned_text is None
        assert reset.error_message is None
        assert reset.processing_stage is None

    def test_returns_new_instance(self) -> None:
        source = _make_source()
        reset = source.reset_to_initial_state()
        assert reset is not source
