from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from backend.application.use_cases.enqueue_phrase_polish import EnqueuePhrasePolishUseCase
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import PhrasePolishNotSupportedError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.job_type import JobType
from backend.domain.value_objects.source_status import SourceStatus


def _candidate(cid: int, status: CandidateStatus, polished: str | None = None) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=9,
        lemma="stale",
        pos="ADJ",
        cefr_level="B2",
        zipf_frequency=3.5,
        context_fragment="The air was stale",
        fragment_purity="clean",
        occurrences=1,
        status=status,
        polished_fragment=polished,
    )


def _use_case(
    candidates: list[StoredCandidate], content_type: ContentType = ContentType.TEXT,
) -> tuple[EnqueuePhrasePolishUseCase, MagicMock, MagicMock]:
    candidate_repo = MagicMock()
    candidate_repo.get_by_source.return_value = candidates
    candidate_repo.get_by_id.side_effect = lambda cid: next(c for c in candidates if c.id == cid)
    source_repo = MagicMock()
    source_repo.get_by_id.return_value = Source(
        id=9, raw_text="t", status=SourceStatus.DONE,
        input_method=InputMethod.TEXT_PASTED, content_type=content_type,
    )
    sorter = MagicMock()
    sorter.sort.side_effect = lambda cs, _source, _order: cs
    job_repo = MagicMock()
    use_case = EnqueuePhrasePolishUseCase(
        candidate_repo=candidate_repo, source_repo=source_repo,
        candidate_sorter=sorter, job_repo=job_repo,
    )
    return use_case, candidate_repo, job_repo


@pytest.mark.unit
def test_queues_active_cards_ai_has_not_seen() -> None:
    use_case, _, job_repo = _use_case([
        _candidate(1, CandidateStatus.PENDING),
        _candidate(2, CandidateStatus.LEARN),
        _candidate(3, CandidateStatus.KNOWN),
        _candidate(4, CandidateStatus.PENDING, polished="The air was stale"),
    ])

    assert use_case.execute(9) == 2

    jobs = job_repo.create_bulk.call_args.args[0]
    assert [j.candidate_id for j in jobs] == [1, 2]
    assert {j.job_type for j in jobs} == {JobType.POLISH}


@pytest.mark.unit
def test_video_source_is_refused() -> None:
    use_case, _, job_repo = _use_case([_candidate(1, CandidateStatus.PENDING)], ContentType.VIDEO)

    with pytest.raises(PhrasePolishNotSupportedError):
        use_case.execute(9)
    job_repo.create_bulk.assert_not_called()


@pytest.mark.unit
def test_polish_again_drops_old_polish_and_queues_the_card() -> None:
    use_case, candidate_repo, job_repo = _use_case(
        [_candidate(4, CandidateStatus.PENDING, polished="The air was bad")],
    )

    use_case.execute_one(4)

    candidate_repo.set_polished_fragment.assert_called_once_with(4, None)
    assert [j.candidate_id for j in job_repo.create_bulk.call_args.args[0]] == [4]
