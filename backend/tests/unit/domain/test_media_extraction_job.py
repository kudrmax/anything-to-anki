import pytest
from backend.domain.entities.media_extraction_job import MediaExtractionJob
from backend.domain.value_objects.media_extraction_job_status import MediaExtractionJobStatus


@pytest.mark.unit
class TestMediaExtractionJob:
    def test_default_counts(self) -> None:
        job = MediaExtractionJob(
            source_id=1,
            status=MediaExtractionJobStatus.PENDING,
            total_candidates=5,
            candidate_ids=[1, 2, 3, 4, 5],
        )
        assert job.processed_candidates == 0
        assert job.failed_candidates == 0
        assert job.skipped_candidates == 0
        assert job.id is None

    def test_status_values(self) -> None:
        assert MediaExtractionJobStatus.PENDING.value == "pending"
        assert MediaExtractionJobStatus.RUNNING.value == "running"
        assert MediaExtractionJobStatus.DONE.value == "done"
        assert MediaExtractionJobStatus.FAILED.value == "failed"
