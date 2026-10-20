import pytest
from backend.domain.services.source_review_status import (
    derive_review_status,
    stored_status_of_set,
)
from backend.domain.value_objects.decision_progress import DecisionProgress
from backend.domain.value_objects.review_status import ReviewStatus
from backend.domain.value_objects.source_status import SourceStatus


@pytest.mark.unit
class TestDeriveReviewStatus:
    def test_some_cards_done_mean_partially_reviewed(self) -> None:
        result = derive_review_status(SourceStatus.DONE, DecisionProgress(decided=1, total=2))
        assert result is ReviewStatus.PARTIALLY_REVIEWED

    def test_untouched_source_is_not_started(self) -> None:
        progress = DecisionProgress(decided=0, total=2)
        assert derive_review_status(SourceStatus.DONE, progress) is ReviewStatus.DONE

    def test_every_card_done_means_reviewed(self) -> None:
        progress = DecisionProgress(decided=3, total=3)
        assert derive_review_status(SourceStatus.DONE, progress) is ReviewStatus.REVIEWED

    def test_the_status_follows_the_progress_both_ways(self) -> None:
        """Nothing is remembered: an undone card reopens a reviewed source, and undoing
        every decision makes it not started again."""
        statuses = [
            derive_review_status(SourceStatus.DONE, DecisionProgress(decided=d, total=2))
            for d in (2, 1, 0)
        ]
        assert statuses == [
            ReviewStatus.REVIEWED, ReviewStatus.PARTIALLY_REVIEWED, ReviewStatus.DONE,
        ]

    @pytest.mark.parametrize(("stored", "shown"), [
        (SourceStatus.NEW, ReviewStatus.NEW), (SourceStatus.ERROR, ReviewStatus.ERROR),
    ])
    def test_sources_outside_review_read_as_stored(
        self, stored: SourceStatus, shown: ReviewStatus,
    ) -> None:
        assert derive_review_status(stored, DecisionProgress(decided=1, total=1)) is shown

    def test_source_with_nothing_ready_is_reviewed(self) -> None:
        assert derive_review_status(SourceStatus.DONE, DecisionProgress()) is ReviewStatus.REVIEWED


@pytest.mark.unit
def test_only_processing_outcomes_are_stored() -> None:
    assert {s.value for s in SourceStatus} == {"new", "done", "error"}


@pytest.mark.unit
@pytest.mark.parametrize(("statuses", "expected"), [
    ([], SourceStatus.NEW),
    ([SourceStatus.ERROR, SourceStatus.DONE], SourceStatus.DONE),
    ([SourceStatus.ERROR, SourceStatus.ERROR], SourceStatus.ERROR),
    ([SourceStatus.ERROR, SourceStatus.NEW], SourceStatus.NEW),
    ([SourceStatus.DONE], SourceStatus.DONE),
])
def test_stored_status_of_set(statuses: list[SourceStatus], expected: SourceStatus) -> None:
    assert stored_status_of_set(statuses) is expected
