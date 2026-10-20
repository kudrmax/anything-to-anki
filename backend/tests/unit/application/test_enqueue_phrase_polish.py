from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.enqueue_phrase_polish import EnqueuePhrasePolishUseCase
from backend.application.utils.requested_cards import RequestedCards
from backend.domain.entities.source import Source
from backend.domain.exceptions import PhrasePolishNotSupportedError, SourceOperationBusyError
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_operation_kind import SourceOperationKind
from backend.domain.value_objects.source_status import SourceStatus

from tests.phrase_support import make_occurrence

_STAMPER = MagicMock()
_STAMPER.earned.return_value = CandidateSection.EXTRA
SOURCE_ID = 9
WORD_ID = 4
PHRASE_ID = 40


def _use_case(
    source_format: Format = Format.PLAIN, busy_with: SourceOperationKind | None = None,
) -> tuple[EnqueuePhrasePolishUseCase, MagicMock, MagicMock]:
    shown = replace(
        make_occurrence(polished_text="The air was bad", candidate_id=WORD_ID),
        id=PHRASE_ID, revision=1,
    )
    occurrence_repo = MagicMock()
    occurrence_repo.get.return_value = shown
    candidate_repo = MagicMock()
    candidate_repo.get_by_id.return_value = MagicMock(id=WORD_ID, source_id=SOURCE_ID)
    lock = MagicMock()
    lock.held.return_value = busy_with
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = Source(
        id=SOURCE_ID, status=SourceStatus.DONE, format=source_format, kind=Kind.TEXT,
    )
    job_repo = MagicMock()
    use_case = EnqueuePhrasePolishUseCase(
        cards=RequestedCards(candidate_repo, occurrence_repo, lock),
        occurrence_repo=occurrence_repo, source_repo=source_repo, job_repo=job_repo,
        stamper=_STAMPER,
    )
    return use_case, occurrence_repo, job_repo


@pytest.mark.unit
def test_video_source_is_refused() -> None:
    use_case, _, job_repo = _use_case(Format.VIDEO_FILE)

    with pytest.raises(PhrasePolishNotSupportedError):
        use_case.execute(PHRASE_ID)
    job_repo.enqueue.assert_not_called()


@pytest.mark.unit
def test_polish_again_drops_old_polish_and_queues_the_phrase() -> None:
    use_case, occurrence_repo, job_repo = _use_case()
    shown = occurrence_repo.get.return_value
    occurrence_repo.get.side_effect = [shown, replace(shown, polished_phrase=None, revision=2)]

    use_case.execute(PHRASE_ID)

    occurrence_repo.write_text.assert_called_once_with(
        PHRASE_ID, shown.source_phrase, None, earned_section=CandidateSection.EXTRA,
        polished=None,
    )
    [job] = job_repo.enqueue.call_args.args[0]
    assert (job.job_type, job.candidate_id, job.phrase_id, job.phrase_revision) == (
        JobType.POLISH, WORD_ID, PHRASE_ID, 2,
    )


@pytest.mark.unit
def test_busy_source_is_refused() -> None:
    use_case, occurrence_repo, job_repo = _use_case(busy_with=SourceOperationKind.UPDATE)

    with pytest.raises(SourceOperationBusyError):
        use_case.execute(PHRASE_ID)
    occurrence_repo.write_text.assert_not_called()
    job_repo.enqueue.assert_not_called()
