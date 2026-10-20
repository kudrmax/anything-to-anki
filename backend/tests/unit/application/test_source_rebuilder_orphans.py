"""A rebuild hands the phrases it deletes to the Anki bindings before it deletes them: a
binding of a phrase that goes keeps its card's choice (spec §2)."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from backend.application.utils.source_rebuilder import AnalysedSource, SourceRebuilder
from backend.domain.services.rebuild_plan import AppliedPlan, RebuildPlan
from backend.domain.value_objects.rebuild_mode import RebuildMode

pytestmark = pytest.mark.unit

SOURCE = 7
DELETED = (501, 502)


def test_the_deleted_phrases_are_orphaned_before_the_plan_is_written() -> None:
    order = MagicMock()
    occurrences, anki_sync = MagicMock(), MagicMock()
    order.attach_mock(anki_sync.orphan, "orphan")
    order.attach_mock(occurrences.apply_plan, "apply_plan")
    occurrences.apply_plan.return_value = AppliedPlan(inserted=[], dropped_files=[])
    rebuilder = SourceRebuilder(
        source_repo=MagicMock(), document_repo=MagicMock(), occurrence_repo=occurrences,
        anki_sync=anki_sync, job_repo=MagicMock(), media_repo=MagicMock(),
        media_files=MagicMock(), settings_repo=MagicMock(), vocabulary=MagicMock(),
        threshold_resolver=MagicMock(), stamper=MagicMock(), analyze_text_use_case=MagicMock(),
        unit_of_work=MagicMock(), weight_unknown=1,
    )
    plan = RebuildPlan(source_id=SOURCE, occ_to_delete=DELETED)

    with patch.object(SourceRebuilder, "plan", return_value=plan):
        rebuilder.apply(AnalysedSource(SOURCE, None, None), RebuildMode.UPDATE)

    assert order.mock_calls == [call.orphan(DELETED), call.apply_plan(plan)]
