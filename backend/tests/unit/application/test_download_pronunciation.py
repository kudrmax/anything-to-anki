from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from backend.application.use_cases.download_pronunciation import (
    DownloadPronunciationUseCase,
)
from backend.domain.entities.candidate_pronunciation import CandidatePronunciation
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.enrichment_status import EnrichmentStatus


def _make_candidate(cid: int = 1, source_id: int = 10) -> StoredCandidate:
    return StoredCandidate(
        id=cid,
        source_id=source_id,
        lemma="elaborate",
        surface_form="elaborate",
        pos="VERB",
        context_fragment="Could you elaborate on that?",
        status=CandidateStatus.PENDING,
        cefr_level=None,
        zipf_frequency=4.5,
        fragment_purity="clean",
        occurrences=1,
        is_phrasal_verb=False,
        meaning=None,
        media=None,
    )


def _running_pronunciation(candidate_id: int) -> CandidatePronunciation:
    return CandidatePronunciation(
        candidate_id=candidate_id,
        us_audio_path=None,
        uk_audio_path=None,
        status=EnrichmentStatus.RUNNING,
        error=None,
        generated_at=None,
    )


def _cancelled_pronunciation(candidate_id: int) -> CandidatePronunciation:
    return CandidatePronunciation(
        candidate_id=candidate_id,
        us_audio_path=None,
        uk_audio_path=None,
        status=EnrichmentStatus.CANCELLED,
        error=None,
        generated_at=None,
    )


def _build_use_case(
    candidate_repo: MagicMock,
    pronunciation_repo: MagicMock,
    pronunciation_source: MagicMock,
    media_root: str,
) -> DownloadPronunciationUseCase:
    return DownloadPronunciationUseCase(
        candidate_repo=candidate_repo,
        pronunciation_repo=pronunciation_repo,
        pronunciation_source=pronunciation_source,
        media_root=media_root,
    )


@pytest.mark.unit
@patch("backend.application.use_cases.download_pronunciation.download_file")
def test_downloads_both_us_and_uk(mock_dl: MagicMock, tmp_path: Path) -> None:
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate = _make_candidate(cid=1, source_id=10)
    candidate_repo.get_by_id.return_value = candidate
    pronunciation_repo.get_by_candidate_id.return_value = _running_pronunciation(1)
    pronunciation_source.get_audio_urls.return_value = (
        "https://example.com/us.mp3",
        "https://example.com/uk.mp3",
    )

    uc = _build_use_case(candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path))
    uc.execute_one(1)

    assert mock_dl.call_count == 2
    pronunciation_repo.upsert.assert_called_once()
    upserted: CandidatePronunciation = pronunciation_repo.upsert.call_args[0][0]
    assert upserted.status == EnrichmentStatus.DONE
    assert upserted.us_audio_path is not None
    assert upserted.uk_audio_path is not None
    assert upserted.us_audio_path.endswith("1_pron_us.mp3")
    assert upserted.uk_audio_path.endswith("1_pron_uk.mp3")


@pytest.mark.unit
@patch("backend.application.use_cases.download_pronunciation.download_file")
def test_no_audio_available(mock_dl: MagicMock, tmp_path: Path) -> None:
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    pronunciation_repo.get_by_candidate_id.return_value = _running_pronunciation(1)
    pronunciation_source.get_audio_urls.return_value = (None, None)

    uc = _build_use_case(candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path))
    uc.execute_one(1)

    mock_dl.assert_not_called()
    pronunciation_repo.upsert.assert_called_once()
    upserted: CandidatePronunciation = pronunciation_repo.upsert.call_args[0][0]
    assert upserted.status == EnrichmentStatus.DONE
    assert upserted.us_audio_path is None
    assert upserted.uk_audio_path is None


@pytest.mark.unit
@patch("backend.application.use_cases.download_pronunciation.download_file")
def test_skips_if_cancelled(mock_dl: MagicMock, tmp_path: Path) -> None:
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    pronunciation_repo.get_by_candidate_id.return_value = _cancelled_pronunciation(1)

    uc = _build_use_case(candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path))
    uc.execute_one(1)

    mock_dl.assert_not_called()
    pronunciation_source.get_audio_urls.assert_not_called()
    pronunciation_repo.upsert.assert_not_called()


@pytest.mark.unit
@patch("backend.application.use_cases.download_pronunciation.download_file")
def test_only_us_audio(mock_dl: MagicMock, tmp_path: Path) -> None:
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    pronunciation_repo.get_by_candidate_id.return_value = _running_pronunciation(1)
    pronunciation_source.get_audio_urls.return_value = ("https://example.com/us.mp3", None)

    uc = _build_use_case(candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path))
    uc.execute_one(1)

    assert mock_dl.call_count == 1
    pronunciation_repo.upsert.assert_called_once()
    upserted: CandidatePronunciation = pronunciation_repo.upsert.call_args[0][0]
    assert upserted.status == EnrichmentStatus.DONE
    assert upserted.us_audio_path is not None
    assert upserted.uk_audio_path is None


@pytest.mark.unit
@patch("backend.application.use_cases.download_pronunciation.download_file")
def test_candidate_not_found(mock_dl: MagicMock, tmp_path: Path) -> None:
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate_repo.get_by_id.return_value = None

    uc = _build_use_case(candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path))
    uc.execute_one(999)

    mock_dl.assert_not_called()
    pronunciation_source.get_audio_urls.assert_not_called()
    pronunciation_repo.upsert.assert_not_called()
