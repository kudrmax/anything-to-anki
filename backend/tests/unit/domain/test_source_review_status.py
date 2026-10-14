import pytest
from backend.domain.services.source_review_status import derive_review_status
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestDeriveReviewStatus:
    def test_pending_candidates_mean_partially_reviewed(self) -> None:
        result = derive_review_status(SourceStatus.DONE, DecisionProgress(decided=1, total=2))
        assert result == SourceStatus.PARTIALLY_REVIEWED

    def test_untouched_source_stays_not_started(self) -> None:
        progress = DecisionProgress(decided=0, total=2)
        assert derive_review_status(SourceStatus.DONE, progress) == SourceStatus.DONE

    def test_no_pending_candidates_mean_reviewed(self) -> None:
        progress = DecisionProgress(decided=3, total=3)
        result = derive_review_status(SourceStatus.PARTIALLY_REVIEWED, progress)
        assert result == SourceStatus.REVIEWED

    def test_new_pending_candidate_reopens_a_reviewed_source(self) -> None:
        result = derive_review_status(SourceStatus.REVIEWED, DecisionProgress(decided=1, total=2))
        assert result == SourceStatus.PARTIALLY_REVIEWED

    @pytest.mark.parametrize(
        "status", [SourceStatus.NEW, SourceStatus.ERROR],
    )
    def test_sources_outside_review_keep_their_status(self, status: SourceStatus) -> None:
        assert derive_review_status(status, DecisionProgress(decided=1, total=1)) == status

    def test_source_with_nothing_ready_is_reviewed(self) -> None:
        assert derive_review_status(SourceStatus.DONE, DecisionProgress()) == SourceStatus.REVIEWED
