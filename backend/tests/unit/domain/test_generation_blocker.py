from __future__ import annotations

import pytest
from backend.domain.services.generation_blocker import set_blocker
from backend.domain.value_objects.generation_blocker import GenerationBlocker

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("blockers", "expected"), [
    ([None, GenerationBlocker.VIDEO_NOT_DOWNLOADED], None),
    (
        [GenerationBlocker.VIDEO_NOT_DOWNLOADED, GenerationBlocker.VIDEO_DOWNLOADING],
        GenerationBlocker.VIDEO_DOWNLOADING,
    ),
    ([GenerationBlocker.VIDEO_NOT_DOWNLOADED], GenerationBlocker.VIDEO_NOT_DOWNLOADED),
    ([], None),
])
def test_set_blocker(
    blockers: list[GenerationBlocker | None], expected: GenerationBlocker | None,
) -> None:
    assert set_blocker(blockers) is expected
