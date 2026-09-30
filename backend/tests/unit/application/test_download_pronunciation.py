from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from pathlib import Path

    from backend.domain.entities.candidate_pronunciation import CandidatePronunciation

import pytest
from backend.application.use_cases.download_pronunciation import (
    DownloadPronunciationUseCase,
)
from backend.domain.entities.stored_candidate import StoredCandidate
from backend.domain.value_objects.candidate_status import CandidateStatus


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


def _build_use_case(
    candidate_repo: MagicMock,
    pronunciation_repo: MagicMock,
    pronunciation_source: MagicMock,
    media_root: str,
    file_downloader: MagicMock,
) -> DownloadPronunciationUseCase:
    return DownloadPronunciationUseCase(
        candidate_repo=candidate_repo,
        pronunciation_repo=pronunciation_repo,
        pronunciation_source=pronunciation_source,
        file_downloader=file_downloader,
        media_root=media_root,
    )


@pytest.mark.unit
def test_downloads_both_us_and_uk(tmp_path: Path) -> None:
    file_downloader = MagicMock()
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate = _make_candidate(cid=1, source_id=10)
    candidate_repo.get_by_id.return_value = candidate
    pronunciation_source.get_audio_urls.return_value = (
        "https://example.com/us.mp3",
        "https://example.com/uk.mp3",
    )

    uc = _build_use_case(
        candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path), file_downloader,
    )
    uc.execute_one(1)

    assert file_downloader.download.call_count == 2
    pronunciation_repo.upsert.assert_called_once()
    upserted: CandidatePronunciation = pronunciation_repo.upsert.call_args[0][0]
    assert upserted.us_audio_path is not None
    assert upserted.uk_audio_path is not None
    assert upserted.us_audio_path.endswith("1_pron_us.mp3")
    assert upserted.uk_audio_path.endswith("1_pron_uk.mp3")


@pytest.mark.unit
def test_no_audio_available(tmp_path: Path) -> None:
    file_downloader = MagicMock()
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    pronunciation_source.get_audio_urls.return_value = (None, None)

    uc = _build_use_case(
        candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path), file_downloader,
    )
    uc.execute_one(1)

    file_downloader.download.assert_not_called()
    pronunciation_repo.upsert.assert_called_once()
    upserted: CandidatePronunciation = pronunciation_repo.upsert.call_args[0][0]
    assert upserted.us_audio_path is None
    assert upserted.uk_audio_path is None


@pytest.mark.unit
def test_only_us_audio(tmp_path: Path) -> None:
    file_downloader = MagicMock()
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate_repo.get_by_id.return_value = _make_candidate()
    pronunciation_source.get_audio_urls.return_value = ("https://example.com/us.mp3", None)

    uc = _build_use_case(
        candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path), file_downloader,
    )
    uc.execute_one(1)

    assert file_downloader.download.call_count == 1
    pronunciation_repo.upsert.assert_called_once()
    upserted: CandidatePronunciation = pronunciation_repo.upsert.call_args[0][0]
    assert upserted.us_audio_path is not None
    assert upserted.uk_audio_path is None


@pytest.mark.unit
def test_candidate_not_found(tmp_path: Path) -> None:
    file_downloader = MagicMock()
    candidate_repo = MagicMock()
    pronunciation_repo = MagicMock()
    pronunciation_source = MagicMock()

    candidate_repo.get_by_id.return_value = None

    uc = _build_use_case(
        candidate_repo, pronunciation_repo, pronunciation_source, str(tmp_path), file_downloader,
    )
    uc.execute_one(999)

    file_downloader.download.assert_not_called()
    pronunciation_source.get_audio_urls.assert_not_called()
    pronunciation_repo.upsert.assert_not_called()
