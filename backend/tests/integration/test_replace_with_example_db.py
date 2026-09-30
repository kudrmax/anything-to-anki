"""Integration test: a candidate replaced with an example keeps its CEFR level.

The level is not stored on the candidate — it is derived from the breakdown
row on load, so the replacement must be persisted together with a breakdown.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from backend.application.use_cases.replace_with_example import ReplaceWithExampleUseCase
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.cefr_breakdown import CEFRBreakdown, SourceVote
from backend.domain.value_objects.cefr_level import CEFRLevel
from backend.domain.value_objects.usage_distribution import UsageDistribution
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

USAGE_GROUPS = {"informal": 1.0}


def _breakdown() -> CEFRBreakdown:
    vote = SourceVote(
        source_name="Oxford 5000",
        distribution={CEFRLevel.B1: 1.0},
        top_level=CEFRLevel.B1,
    )
    return CEFRBreakdown(
        final_level=CEFRLevel.B1,
        decision_method="priority",
        priority_votes=[vote],
        votes=[],
    )


@pytest.mark.integration
def test_replacement_keeps_cefr_level_after_reload(db_session: Session, source_id: int) -> None:
    repo = SqlaCandidateRepository(db_session)
    original = repo.create_batch([
        StoredCandidate(
            source_id=source_id,
            lemma="advance",
            pos="NOUN",
            cefr_level="B1",
            zipf_frequency=4.0,
            context_fragment="in advance of the meeting",
            fragment_purity="clean",
            occurrences=1,
            status=CandidateStatus.PENDING,
            cefr_breakdown=_breakdown(),
            usage_distribution=UsageDistribution(groups=USAGE_GROUPS),
        )
    ])[0]
    assert original.id is not None

    result = ReplaceWithExampleUseCase(candidate_repo=repo).execute(
        candidate_id=original.id, example_text="She paid in advance.",
    )
    db_session.expire_all()

    reloaded = repo.get_by_id(result.id)
    assert reloaded is not None
    assert reloaded.cefr_level == "B1"
    assert reloaded.cefr_breakdown is not None
    assert reloaded.cefr_breakdown.decision_method == "priority"
    assert reloaded.usage_distribution == UsageDistribution(groups=USAGE_GROUPS)
