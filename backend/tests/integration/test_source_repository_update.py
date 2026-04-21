import pytest
from backend.domain.entities.source import Source
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.input_method import InputMethod
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
                raw_text="Original text",
                status=SourceStatus.NEW,
                input_method=InputMethod.TEXT_PASTED,
                content_type=ContentType.TEXT,
                title="Original title",
            )
        )
        assert source.id is not None

        # Simulate processing: update to DONE with cleaned_text
        repo.update_status(
            source.id,
            SourceStatus.DONE,
            cleaned_text="Cleaned text",
            processing_stage=ProcessingStage.ANALYZING_TEXT,
        )

        done = repo.get_by_id(source.id)
        assert done is not None
        assert done.status == SourceStatus.DONE
        assert done.cleaned_text == "Cleaned text"
        assert done.processing_stage == ProcessingStage.ANALYZING_TEXT

        # Reset to initial state and persist via update_source
        reset = done.reset_to_initial_state()
        assert reset.status == SourceStatus.NEW
        assert reset.cleaned_text is None
        assert reset.processing_stage is None
        assert reset.error_message is None

        repo.update_source(reset)

        # Verify all fields were persisted
        refreshed = repo.get_by_id(source.id)
        assert refreshed is not None
        assert refreshed.status == SourceStatus.NEW
        assert refreshed.cleaned_text is None
        assert refreshed.processing_stage is None
        assert refreshed.error_message is None
        assert refreshed.raw_text == "Original text"
        assert refreshed.title == "Original title"

    def test_update_source_with_none_id_does_nothing(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        source = Source(
            raw_text="No id",
            status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED,
            content_type=ContentType.TEXT,
        )
        # Should not raise
        repo.update_source(source)

    def test_update_source_with_missing_id_does_nothing(self, db_session: Session) -> None:
        repo = SqlaSourceRepository(db_session)
        source = Source(
            id=99999,
            raw_text="Ghost",
            status=SourceStatus.NEW,
            input_method=InputMethod.TEXT_PASTED,
            content_type=ContentType.TEXT,
        )
        # Should not raise
        repo.update_source(source)
