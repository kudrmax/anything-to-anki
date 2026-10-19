"""What a source can be brought up to date with."""
from __future__ import annotations

import pytest
from backend.domain.entities.source import Source
from backend.domain.services.source_operations import available_operations
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit

REFRESH = SourceOperationKind.REFRESH
REBUILD = SourceOperationKind.REBUILD


def _source(role: SourceRole, status: SourceStatus) -> Source:
    return Source(id=1, role=role, status=status)


def test_a_topic_offers_refresh_then_rebuild() -> None:
    done_topic = _source(SourceRole.TOPIC, SourceStatus.DONE)

    assert available_operations(done_topic) == (REFRESH, REBUILD)


def test_a_topic_not_processed_offers_nothing() -> None:
    assert available_operations(_source(SourceRole.TOPIC, SourceStatus.NEW)) == ()


def test_saved_phrases_offer_rebuild() -> None:
    assert available_operations(_source(SourceRole.SAVED_PHRASES, SourceStatus.DONE)) == (REBUILD,)


@pytest.mark.parametrize("status", [SourceStatus.DONE, SourceStatus.ERROR])
def test_a_content_source_offers_rebuild_when_done_or_failed(status: SourceStatus) -> None:
    assert available_operations(_source(SourceRole.CONTENT, status)) == (REBUILD,)


def test_a_content_source_not_processed_offers_nothing() -> None:
    assert available_operations(_source(SourceRole.CONTENT, SourceStatus.NEW)) == ()
