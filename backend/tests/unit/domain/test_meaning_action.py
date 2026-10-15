"""What a card offers about its meaning before the meaning text is there."""
from __future__ import annotations

import pytest
from backend.domain.entities.candidate_meaning import CandidateMeaning
from backend.domain.services.meaning_action import MeaningAction, meaning_action
from backend.domain.value_objects.job_status import JobStatus

pytestmark = pytest.mark.unit


def _meaning(text: str | None) -> CandidateMeaning:
    return CandidateMeaning(
        candidate_id=1, meaning=text, translation=None, synonyms=None, examples=None, ipa=None,
        generated_at=None,
    )


@pytest.mark.parametrize(("meaning", "job", "action"), [
    (None, None, MeaningAction.GENERATE),
    (None, JobStatus.QUEUED, MeaningAction.GENERATE),
    (_meaning(None), None, MeaningAction.GENERATE),
    (None, JobStatus.FAILED, MeaningAction.RETRY),
    (None, JobStatus.RUNNING, None),
    (_meaning("to stare"), None, None),
    (_meaning("to stare"), JobStatus.FAILED, None),
])
def test_meaning_action(
    meaning: CandidateMeaning | None, job: JobStatus | None, action: MeaningAction | None,
) -> None:
    assert meaning_action(meaning, job) == action
