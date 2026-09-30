import pytest
from backend.domain.services.source_review_status import derive_review_status
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestDeriveReviewStatus:
    def test_pending_candidates_mean_partially_reviewed(self) -> None:
        statuses = [CandidateStatus.LEARN, CandidateStatus.PENDING]
        result = derive_review_status(SourceStatus.DONE, statuses)
        assert result == SourceStatus.PARTIALLY_REVIEWED

    def test_no_pending_candidates_mean_reviewed(self) -> None:
        statuses = [CandidateStatus.LEARN, CandidateStatus.KNOWN, CandidateStatus.SKIP]
        result = derive_review_status(SourceStatus.PARTIALLY_REVIEWED, statuses)
        assert result == SourceStatus.REVIEWED

    def test_new_pending_candidate_reopens_a_reviewed_source(self) -> None:
        statuses = [CandidateStatus.SKIP, CandidateStatus.PENDING]
        result = derive_review_status(SourceStatus.REVIEWED, statuses)
        assert result == SourceStatus.PARTIALLY_REVIEWED

    @pytest.mark.parametrize(
        "status", [SourceStatus.NEW, SourceStatus.PROCESSING, SourceStatus.ERROR],
    )
    def test_sources_outside_review_keep_their_status(self, status: SourceStatus) -> None:
        assert derive_review_status(status, [CandidateStatus.LEARN]) == status
