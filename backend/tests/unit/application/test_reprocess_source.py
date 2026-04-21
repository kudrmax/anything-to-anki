from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.application.use_cases.reprocess_source import ReprocessSourceUseCase
from backend.domain.entities.source import Source
from backend.domain.exceptions import (
    SourceHasActiveJobsError,
    SourceNotFoundError,
    SourceNotReprocessableError,
)
from backend.domain.value_objects.content_type import ContentType
from backend.domain.value_objects.enrichment_status import EnrichmentStatus
from backend.domain.value_objects.input_method import InputMethod
from backend.domain.value_objects.source_status import SourceStatus


def _make_use_case() -> tuple[ReprocessSourceUseCase, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock, MagicMock]:
    source_repo = MagicMock()
    candidate_repo = MagicMock()
    meaning_repo = MagicMock()
    media_repo = MagicMock()
    pronunciation_repo = MagicMock()
    process_source_uc = MagicMock()

    uc = ReprocessSourceUseCase(
        source_repo=source_repo,
        candidate_repo=candidate_repo,
        meaning_repo=meaning_repo,
        media_repo=media_repo,
        pronunciation_repo=pronunciation_repo,
        process_source_use_case=process_source_uc,
    )
    return uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc


def _source(status: SourceStatus) -> Source:
    return Source(
        id=1,
        raw_text="Hello world",
        status=status,
        input_method=InputMethod.TEXT_PASTED,
        content_type=ContentType.TEXT,
        cleaned_text="hello world",
    )


def _no_active_jobs(meaning_repo: MagicMock, media_repo: MagicMock, pronunciation_repo: MagicMock) -> None:
    for repo in (meaning_repo, media_repo, pronunciation_repo):
        repo.get_candidate_ids_by_status.return_value = []


@pytest.mark.unit
class TestReprocessSourceUseCase:
    def test_reprocess_done_source(self) -> None:
        uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc = _make_use_case()
        source_repo.get_by_id.return_value = _source(SourceStatus.DONE)
        _no_active_jobs(meaning_repo, media_repo, pronunciation_repo)

        uc.execute(1)

        candidate_repo.delete_by_source.assert_called_once_with(1)
        updated: Source = source_repo.update_source.call_args[0][0]
        assert updated.status == SourceStatus.NEW
        assert updated.cleaned_text is None
        process_source_uc.start.assert_called_once_with(1)

    def test_reprocess_error_source(self) -> None:
        uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc = _make_use_case()
        source_repo.get_by_id.return_value = _source(SourceStatus.ERROR)
        _no_active_jobs(meaning_repo, media_repo, pronunciation_repo)

        uc.execute(1)

        candidate_repo.delete_by_source.assert_called_once_with(1)
        updated: Source = source_repo.update_source.call_args[0][0]
        assert updated.status == SourceStatus.NEW
        assert updated.cleaned_text is None
        process_source_uc.start.assert_called_once_with(1)

    def test_reprocess_reviewed_source(self) -> None:
        uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc = _make_use_case()
        source_repo.get_by_id.return_value = _source(SourceStatus.REVIEWED)
        _no_active_jobs(meaning_repo, media_repo, pronunciation_repo)

        uc.execute(1)

        candidate_repo.delete_by_source.assert_called_once_with(1)
        process_source_uc.start.assert_called_once_with(1)

    def test_reprocess_partially_reviewed_source(self) -> None:
        uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc = _make_use_case()
        source_repo.get_by_id.return_value = _source(SourceStatus.PARTIALLY_REVIEWED)
        _no_active_jobs(meaning_repo, media_repo, pronunciation_repo)

        uc.execute(1)

        candidate_repo.delete_by_source.assert_called_once_with(1)
        process_source_uc.start.assert_called_once_with(1)

    def test_reprocess_new_source_raises(self) -> None:
        uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc = _make_use_case()
        source_repo.get_by_id.return_value = _source(SourceStatus.NEW)

        with pytest.raises(SourceNotReprocessableError):
            uc.execute(1)

        candidate_repo.delete_by_source.assert_not_called()
        process_source_uc.start.assert_not_called()

    def test_reprocess_processing_source_raises(self) -> None:
        uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc = _make_use_case()
        source_repo.get_by_id.return_value = _source(SourceStatus.PROCESSING)

        with pytest.raises(SourceNotReprocessableError):
            uc.execute(1)

        candidate_repo.delete_by_source.assert_not_called()
        process_source_uc.start.assert_not_called()

    def test_not_found(self) -> None:
        uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc = _make_use_case()
        source_repo.get_by_id.return_value = None

        with pytest.raises(SourceNotFoundError):
            uc.execute(999)

        candidate_repo.delete_by_source.assert_not_called()
        process_source_uc.start.assert_not_called()

    def test_active_jobs_raises(self) -> None:
        uc, source_repo, candidate_repo, meaning_repo, media_repo, pronunciation_repo, process_source_uc = _make_use_case()
        source_repo.get_by_id.return_value = _source(SourceStatus.DONE)

        # meaning_repo returns active candidates for RUNNING status
        def meaning_ids_by_status(source_id: int, status: EnrichmentStatus) -> list[int]:
            if status == EnrichmentStatus.RUNNING:
                return [10]
            return []

        meaning_repo.get_candidate_ids_by_status.side_effect = meaning_ids_by_status
        media_repo.get_candidate_ids_by_status.return_value = []
        pronunciation_repo.get_candidate_ids_by_status.return_value = []

        with pytest.raises(SourceHasActiveJobsError):
            uc.execute(1)

        candidate_repo.delete_by_source.assert_not_called()
        process_source_uc.start.assert_not_called()
