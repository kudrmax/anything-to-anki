from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from backend.application.use_cases.get_reprocess_stats import GetReprocessStatsUseCase
from backend.application.use_cases.reprocess_source import ReprocessSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.exceptions import SourceHasActiveJobsError
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)
from backend.infrastructure.persistence.sqla_candidate_media_repository import (
    SqlaCandidateMediaRepository,
)
from backend.infrastructure.persistence.sqla_candidate_pronunciation_repository import (
    SqlaCandidatePronunciationRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from backend.infrastructure.persistence.sqla_source_repository import (
    SqlaSourceRepository,
)


def _create_processed_source(db_session: Session) -> int:
    """Create a source in DONE state with 3 candidates (LEARN, KNOWN, SKIP)."""
    source_repo = SqlaSourceRepository(db_session)
    candidate_repo = SqlaCandidateRepository(db_session)

    source = source_repo.create(
        Source(
            raw_text="She tends to procrastinate when facing deadlines.",
            status=SourceStatus.DONE,
            input_method=InputMethod.TEXT_PASTED,
            content_type=ContentType.TEXT,
            cleaned_text="She tends to procrastinate when facing deadlines.",
        )
    )
    assert source.id is not None

    candidates = [
        StoredCandidate(
            source_id=source.id,
            lemma="procrastinate",
            pos="VERB",
            cefr_level="C1",
            zipf_frequency=3.2,
            context_fragment="She tends to procrastinate when facing deadlines.",
            fragment_purity="pure",
            occurrences=1,
            status=CandidateStatus.LEARN,
        ),
        StoredCandidate(
            source_id=source.id,
            lemma="deadline",
            pos="NOUN",
            cefr_level="B2",
            zipf_frequency=4.5,
            context_fragment="She tends to procrastinate when facing deadlines.",
            fragment_purity="pure",
            occurrences=1,
            status=CandidateStatus.KNOWN,
        ),
        StoredCandidate(
            source_id=source.id,
            lemma="tend",
            pos="VERB",
            cefr_level="A2",
            zipf_frequency=5.1,
            context_fragment="She tends to procrastinate when facing deadlines.",
            fragment_purity="pure",
            occurrences=1,
            status=CandidateStatus.SKIP,
        ),
    ]
    candidate_repo.create_batch(candidates)

    return source.id


def _make_reprocess_uc(
    db_session: Session,
    process_source_uc: MagicMock,
) -> ReprocessSourceUseCase:
    return ReprocessSourceUseCase(
        source_repo=SqlaSourceRepository(db_session),
        candidate_repo=SqlaCandidateRepository(db_session),
        meaning_repo=SqlaCandidateMeaningRepository(db_session),
        media_repo=SqlaCandidateMediaRepository(db_session),
        pronunciation_repo=SqlaCandidatePronunciationRepository(db_session),
        process_source_use_case=process_source_uc,
    )


def _make_stats_uc(db_session: Session) -> GetReprocessStatsUseCase:
    from backend.infrastructure.persistence.sqla_known_word_repository import (
        SqlaKnownWordRepository,
    )
    return GetReprocessStatsUseCase(
        source_repo=SqlaSourceRepository(db_session),
        candidate_repo=SqlaCandidateRepository(db_session),
        known_word_repo=SqlaKnownWordRepository(db_session),
        meaning_repo=SqlaCandidateMeaningRepository(db_session),
        media_repo=SqlaCandidateMediaRepository(db_session),
        pronunciation_repo=SqlaCandidatePronunciationRepository(db_session),
    )


@pytest.mark.integration
def test_full_reprocess_cycle(db_session: Session) -> None:
    source_id = _create_processed_source(db_session)

    candidate_repo = SqlaCandidateRepository(db_session)
    source_repo = SqlaSourceRepository(db_session)

    # Verify 3 candidates exist
    candidates_before = candidate_repo.get_by_source(source_id)
    assert len(candidates_before) == 3

    # Get stats
    stats_uc = _make_stats_uc(db_session)
    stats = stats_uc.execute(source_id)
    assert stats.learn_count == 1
    assert stats.known_count == 1
    assert stats.skip_count == 1
    assert stats.has_active_jobs is False

    # Reprocess with mocked ProcessSourceUseCase
    process_source_uc = MagicMock()
    reprocess_uc = _make_reprocess_uc(db_session, process_source_uc)
    reprocess_uc.execute(source_id)

    # Old candidates deleted
    candidates_after = candidate_repo.get_by_source(source_id)
    assert len(candidates_after) == 0

    # Source status reset to NEW
    source = source_repo.get_by_id(source_id)
    assert source is not None
    assert source.status == SourceStatus.NEW

    # Source cleaned_text is None
    assert source.cleaned_text is None

    # process_source_uc.start called with source_id
    process_source_uc.start.assert_called_once_with(source_id)


@pytest.mark.integration
def test_reprocess_blocked_by_active_jobs(db_session: Session) -> None:
    source_id = _create_processed_source(db_session)

    candidate_repo = SqlaCandidateRepository(db_session)
    meaning_repo = SqlaCandidateMeaningRepository(db_session)

    # Get first candidate id
    candidates = candidate_repo.get_by_source(source_id)
    assert len(candidates) == 3
    first_candidate_id = candidates[0].id
    assert first_candidate_id is not None

    # Mark a meaning as RUNNING
    meaning_repo.mark_queued_bulk([first_candidate_id])
    meaning_repo.mark_running(first_candidate_id)

    # Attempt reprocess → SourceHasActiveJobsError
    process_source_uc = MagicMock()
    reprocess_uc = _make_reprocess_uc(db_session, process_source_uc)

    with pytest.raises(SourceHasActiveJobsError):
        reprocess_uc.execute(source_id)

    # Verify candidates NOT deleted (still 3)
    candidates_after = candidate_repo.get_by_source(source_id)
    assert len(candidates_after) == 3

    # process_source_uc.start was never called
    process_source_uc.start.assert_not_called()


@pytest.mark.integration
def test_reprocess_error_source_no_candidates(db_session: Session) -> None:
    source_repo = SqlaSourceRepository(db_session)

    # Create source directly in ERROR state (no candidates)
    source = source_repo.create(
        Source(
            raw_text="Some raw text that failed processing.",
            status=SourceStatus.ERROR,
            input_method=InputMethod.TEXT_PASTED,
            content_type=ContentType.TEXT,
            error_message="Processing failed: timeout",
        )
    )
    assert source.id is not None
    source_id = source.id

    # Reprocess → should work
    process_source_uc = MagicMock()
    reprocess_uc = _make_reprocess_uc(db_session, process_source_uc)
    reprocess_uc.execute(source_id)

    # Verify source reset to NEW, error_message cleared
    updated = source_repo.get_by_id(source_id)
    assert updated is not None
    assert updated.status == SourceStatus.NEW
    assert updated.error_message is None

    process_source_uc.start.assert_called_once_with(source_id)
