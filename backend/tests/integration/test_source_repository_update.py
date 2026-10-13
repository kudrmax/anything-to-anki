import pytest
from backend.domain.entities.source import Source
from backend.domain.value_objects.content import Kind
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.processing_stage import ProcessingStage
from backend.domain.value_objects.source_status import SourceStatus
from backend.infrastructure.persistence.sqla_source_repository import (
    SqlaSourceRepository,
)
from sqlalchemy.orm import Session


@pytest.mark.integration
class TestSourceRepositoryUpdateSource:
    def test_update_persists_all_fields(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)

        # Create initial source
        source = repo.create(
            Source(
                status=SourceStatus.NEW,
                title="Original title", format=Format.PLAIN, kind=Kind.TEXT,
            )
        )
        assert source.id is not None

        # Simulate processing
        repo.update_status(
            source.id,
            SourceStatus.DONE,
            processing_stage=ProcessingStage.ANALYZING_TEXT,
        )

        done = repo.get_by_id(source.id)
        assert done is not None
        assert done.status == SourceStatus.DONE
        assert done.processing_stage == ProcessingStage.ANALYZING_TEXT

        # Reset to initial state and persist via update_source
        reset = done.reset_to_initial_state()
        assert reset.status == SourceStatus.NEW
        assert reset.processing_stage is None
        assert reset.error_message is None

        repo.update_source(reset)

        # Verify all fields were persisted
        refreshed = repo.get_by_id(source.id)
        assert refreshed is not None
        assert refreshed.status == SourceStatus.NEW
        assert refreshed.processing_stage is None
        assert refreshed.error_message is None
        assert refreshed.title == "Original title"

    def test_update_source_with_none_id_does_nothing(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        source = Source(
            status=SourceStatus.NEW, format=Format.PLAIN, kind=Kind.TEXT,
            )
        # Should not raise
        repo.update_source(source)

    def test_update_source_with_missing_id_does_nothing(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        source = Source(
            id=99999,
            status=SourceStatus.NEW, format=Format.PLAIN, kind=Kind.TEXT,
            )
        # Should not raise
        repo.update_source(source)
