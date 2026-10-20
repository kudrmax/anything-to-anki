"""What a source can be brought up to date with."""
from __future__ import annotations

import pytest
from backend.domain.entities.source import Source
from backend.domain.services.source_operations import (
    OperationsOffer,
    available_operations,
    operations_offer,
)
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

pytestmark = pytest.mark.unit

REFRESH = SourceOperationKind.REFRESH
UPDATE = SourceOperationKind.UPDATE
RECUT = SourceOperationKind.RECUT


def _source(role: SourceRole, status: SourceStatus) -> Source:
    return Source(id=1, role=role, status=status)


def test_a_topic_offers_refresh_then_update() -> None:
    done_topic = _source(SourceRole.TOPIC, SourceStatus.DONE)

    assert available_operations(done_topic) == (REFRESH, UPDATE)


def test_a_topic_not_processed_offers_nothing() -> None:
    assert available_operations(_source(SourceRole.TOPIC, SourceStatus.NEW)) == ()


def test_saved_phrases_offer_update_only() -> None:
    assert available_operations(_source(SourceRole.SAVED_PHRASES, SourceStatus.DONE)) == (UPDATE,)


@pytest.mark.parametrize("status", [SourceStatus.DONE, SourceStatus.ERROR])
def test_a_content_source_offers_update_and_recut_when_done_or_failed(
    status: SourceStatus,
) -> None:
    assert available_operations(_source(SourceRole.CONTENT, status)) == (UPDATE, RECUT)


def test_a_content_source_not_processed_offers_nothing() -> None:
    assert available_operations(_source(SourceRole.CONTENT, SourceStatus.NEW)) == ()


def test_a_source_offers_what_it_has_as_a_set_of_one() -> None:
    done = Source(id=1, role=SourceRole.CONTENT, status=SourceStatus.DONE)

    assert operations_offer([done], {}) == OperationsOffer(
        (UPDATE, RECUT), can_start=True, hint=None,
    )
    assert operations_offer([done], {1: RECUT}) == OperationsOffer(
        (UPDATE, RECUT), can_start=False, hint="Wait until the rebuild finishes",
    )


def test_a_source_offering_nothing_can_start_while_free() -> None:
    new = Source(id=1, role=SourceRole.CONTENT, status=SourceStatus.NEW)

    assert operations_offer([new], {}) == OperationsOffer((), can_start=True, hint=None)
    assert operations_offer([new], {1: SourceOperationKind.PROCESS}).can_start is False


def test_a_set_offers_the_union_in_menu_order() -> None:
    content = Source(id=1, role=SourceRole.CONTENT, status=SourceStatus.DONE)
    topic = Source(id=2, role=SourceRole.TOPIC, status=SourceStatus.DONE)

    assert operations_offer([content, topic], {}).operations == (REFRESH, UPDATE, RECUT)


def test_a_set_starts_while_one_offering_source_is_free() -> None:
    first = Source(id=1, role=SourceRole.CONTENT, status=SourceStatus.DONE)
    second = Source(id=2, role=SourceRole.CONTENT, status=SourceStatus.DONE)
    new = Source(id=3, role=SourceRole.CONTENT, status=SourceStatus.NEW)

    assert operations_offer([first, second, new], {1: UPDATE}).can_start is True
    blocked = operations_offer([first, second, new], {1: UPDATE, 2: UPDATE})
    assert (blocked.can_start, blocked.hint) == (False, "Wait until the rebuild finishes")


def test_an_empty_set_offers_nothing() -> None:
    assert operations_offer([], {}) == OperationsOffer((), can_start=False, hint=None)
