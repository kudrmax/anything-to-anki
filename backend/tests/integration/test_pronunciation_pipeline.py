"""Integration test: pronunciation download pipeline.

Tests the flow: eligible candidates -> download -> verify stored paths.
Uses in-memory SQLite and mocked HTTP downloads.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_candidate_pronunciation_repository import (
    SqlaCandidatePronunciationRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.word_support import insert_word

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session


def _insert_candidate(session: Session, candidate_id: int, lemma: str, source_id: int = 1) -> None:
    insert_word(
        session, candidate_id, source_id=source_id, lemma=lemma, status="learn",
        phrase_text=f"a {lemma}", zipf_frequency=4.0, is_sweet_spot=True,
    )


@pytest.mark.integration
class TestPronunciationPipeline:
    def setup_method(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)

    def test_full_flow_download_verify(self, tmp_path: Path) -> None:
        """Download pronunciation -> verify stored with paths."""
        from backend.application.use_cases.download_pronunciation import (
            DownloadPronunciationUseCase,
        )

        with self._Session() as session:
            _insert_candidate(session, 1, "hello")
            _insert_candidate(session, 2, "world")
            session.commit()

            pron_repo = SqlaCandidatePronunciationRepository(session)
            candidate_repo = SqlaCandidateRepository(session)

            # Step 1: run download use case
            pron_source = MagicMock()
            pron_source.get_audio_urls.return_value = (
                "https://cdn/us/hello.mp3",
                "https://cdn/uk/hello.mp3",
            )

            use_case = DownloadPronunciationUseCase(
                candidate_repo=candidate_repo,
                pronunciation_repo=pron_repo,
                pronunciation_source=pron_source,
                file_downloader=MagicMock(),
                media_root=str(tmp_path),
                unit_of_work=MagicMock(),
            )

            use_case.execute_one(1)

            session.commit()

            # Step 2: verify result
            word = candidate_repo.get_by_id(1)
            assert word is not None
            result = word.pronunciation
            assert result is not None
            assert result.us_audio_path is not None
            assert "1_pron_us.mp3" in result.us_audio_path
            assert result.uk_audio_path is not None
            assert "1_pron_uk.mp3" in result.uk_audio_path

    def test_no_audio_available(self, tmp_path: Path) -> None:
        """Word not in Cambridge -> stored with no paths."""
        from backend.application.use_cases.download_pronunciation import (
            DownloadPronunciationUseCase,
        )

        with self._Session() as session:
            _insert_candidate(session, 1, "xyznonexistent")
            session.commit()

            pron_repo = SqlaCandidatePronunciationRepository(session)
            candidate_repo = SqlaCandidateRepository(session)

            pron_source = MagicMock()
            pron_source.get_audio_urls.return_value = (None, None)

            use_case = DownloadPronunciationUseCase(
                candidate_repo=candidate_repo,
                pronunciation_repo=pron_repo,
                pronunciation_source=pron_source,
                file_downloader=MagicMock(),
                media_root=str(tmp_path),
                unit_of_work=MagicMock(),
            )

            use_case.execute_one(1)
            session.commit()

            word = candidate_repo.get_by_id(1)
            assert word is not None
            result = word.pronunciation
            assert result is not None
            assert result.us_audio_path is None
            assert result.uk_audio_path is None
