from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models import (
    CandidateMeaningModel,
    SourceModel,
    StoredCandidateModel,
)
from backend.infrastructure.persistence.sqla_candidate_meaning_repository import (
    SqlaCandidateMeaningRepository,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    yield s
    s.close()


def _insert_source(session: Session, source_id: int, title: str = "Test Source") -> None:
    session.add(SourceModel(
        id=source_id,
        raw_text="raw",
        title=title,
        status="done",
        input_method="text_pasted",
        content_type="text",
    ))
    session.flush()


def _insert_candidate(
    session: Session,
    candidate_id: int,
    source_id: int = 1,
) -> None:
    session.add(StoredCandidateModel(
        id=candidate_id,
        source_id=source_id,
        lemma="test",
        pos="NOUN",
        cefr_level="B1",
        zipf_frequency=4.0,
        is_sweet_spot=True,
        context_fragment="a test",
        fragment_purity="clean",
        occurrences=1,
        status=CandidateStatus.LEARN.value,
    ))
    session.flush()


def _insert_meaning(
    session: Session,
    candidate_id: int,
    status: EnrichmentStatus,
    error: str | None = None,
) -> None:
    session.add(CandidateMeaningModel(
        candidate_id=candidate_id,
        meaning=None,
        ipa=None,
        status=status.value,
        error=error,
        generated_at=None,
    ))
    session.flush()


class TestCountByStatusGlobal:
    def test_returns_zero_when_empty(self, session: Session) -> None:
        repo = SqlaCandidateMeaningRepository(session)
        assert repo.count_by_status_global(EnrichmentStatus.FAILED) == 0

    def test_counts_across_all_sources(self, session: Session) -> None:
        _insert_source(session, 1)
        _insert_source(session, 2)
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=1)
        _insert_candidate(session, 3, source_id=2)
        _insert_meaning(session, 1, EnrichmentStatus.FAILED)
        _insert_meaning(session, 2, EnrichmentStatus.DONE)
        _insert_meaning(session, 3, EnrichmentStatus.FAILED)

        repo = SqlaCandidateMeaningRepository(session)
        assert repo.count_by_status_global(EnrichmentStatus.FAILED) == 2
        assert repo.count_by_status_global(EnrichmentStatus.DONE) == 1

    def test_filters_by_source_id(self, session: Session) -> None:
        _insert_source(session, 1)
        _insert_source(session, 2)
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=2)
        _insert_meaning(session, 1, EnrichmentStatus.FAILED)
        _insert_meaning(session, 2, EnrichmentStatus.FAILED)

        repo = SqlaCandidateMeaningRepository(session)
        assert repo.count_by_status_global(EnrichmentStatus.FAILED, source_id=1) == 1
        assert repo.count_by_status_global(EnrichmentStatus.FAILED, source_id=2) == 1
        assert repo.count_by_status_global(EnrichmentStatus.FAILED, source_id=99) == 0


class TestGetFailedGroupedByError:
    def test_returns_empty_when_no_failed(self, session: Session) -> None:
        _insert_source(session, 1)
        _insert_candidate(session, 1, source_id=1)
        _insert_meaning(session, 1, EnrichmentStatus.DONE)

        repo = SqlaCandidateMeaningRepository(session)
        assert repo.get_failed_grouped_by_error() == []

    def test_groups_by_error_text(self, session: Session) -> None:
        _insert_source(session, 1, title="Source A")
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=1)
        _insert_candidate(session, 3, source_id=1)
        _insert_meaning(session, 1, EnrichmentStatus.FAILED, error="timeout")
        _insert_meaning(session, 2, EnrichmentStatus.FAILED, error="timeout")
        _insert_meaning(session, 3, EnrichmentStatus.FAILED, error="rate limit")

        repo = SqlaCandidateMeaningRepository(session)
        groups = repo.get_failed_grouped_by_error()

        assert len(groups) == 2
        by_error = {g.error_text: g for g in groups}

        timeout_group = by_error["timeout"]
        assert timeout_group.count == 2
        assert sorted(timeout_group.candidate_ids) == [1, 2]
        assert len(timeout_group.source_counts) == 1
        assert timeout_group.source_counts[0].source_id == 1
        assert timeout_group.source_counts[0].source_title == "Source A"
        assert timeout_group.source_counts[0].count == 2

        rate_limit_group = by_error["rate limit"]
        assert rate_limit_group.count == 1
        assert rate_limit_group.candidate_ids == [3]

    def test_includes_per_source_breakdown(self, session: Session) -> None:
        _insert_source(session, 1, title="Source 1")
        _insert_source(session, 2, title="Source 2")
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=2)
        _insert_meaning(session, 1, EnrichmentStatus.FAILED, error="crash")
        _insert_meaning(session, 2, EnrichmentStatus.FAILED, error="crash")

        repo = SqlaCandidateMeaningRepository(session)
        groups = repo.get_failed_grouped_by_error()

        assert len(groups) == 1
        group = groups[0]
        assert group.count == 2
        source_ids = {sc.source_id for sc in group.source_counts}
        assert source_ids == {1, 2}

    def test_excludes_non_failed(self, session: Session) -> None:
        _insert_source(session, 1)
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=1)
        _insert_meaning(session, 1, EnrichmentStatus.DONE)
        _insert_meaning(session, 2, EnrichmentStatus.FAILED, error="oops")

        repo = SqlaCandidateMeaningRepository(session)
        groups = repo.get_failed_grouped_by_error()

        assert len(groups) == 1
        assert groups[0].count == 1
        assert groups[0].candidate_ids == [2]

    def test_filters_by_source_id(self, session: Session) -> None:
        _insert_source(session, 1, title="Source 1")
        _insert_source(session, 2, title="Source 2")
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=2)
        _insert_meaning(session, 1, EnrichmentStatus.FAILED, error="timeout")
        _insert_meaning(session, 2, EnrichmentStatus.FAILED, error="timeout")

        repo = SqlaCandidateMeaningRepository(session)
        groups = repo.get_failed_grouped_by_error(source_id=1)

        assert len(groups) == 1
        assert groups[0].candidate_ids == [1]
        assert groups[0].source_counts[0].source_id == 1


class TestGetCandidateIdsByError:
    def test_returns_matching_candidates(self, session: Session) -> None:
        _insert_source(session, 1)
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=1)
        _insert_candidate(session, 3, source_id=1)
        _insert_meaning(session, 1, EnrichmentStatus.FAILED, error="timeout")
        _insert_meaning(session, 2, EnrichmentStatus.FAILED, error="rate limit")
        _insert_meaning(session, 3, EnrichmentStatus.FAILED, error="timeout")

        repo = SqlaCandidateMeaningRepository(session)
        result = repo.get_candidate_ids_by_error("timeout")

        assert sorted(result) == [1, 3]

    def test_returns_empty_for_unknown_error(self, session: Session) -> None:
        repo = SqlaCandidateMeaningRepository(session)
        assert repo.get_candidate_ids_by_error("nonexistent error") == []

    def test_filters_by_source_id(self, session: Session) -> None:
        _insert_source(session, 1)
        _insert_source(session, 2)
        _insert_candidate(session, 1, source_id=1)
        _insert_candidate(session, 2, source_id=2)
        _insert_meaning(session, 1, EnrichmentStatus.FAILED, error="crash")
        _insert_meaning(session, 2, EnrichmentStatus.FAILED, error="crash")

        repo = SqlaCandidateMeaningRepository(session)
        assert repo.get_candidate_ids_by_error("crash", source_id=1) == [1]
        assert repo.get_candidate_ids_by_error("crash", source_id=2) == [2]
