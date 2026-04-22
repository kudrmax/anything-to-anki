"""Integration test: pronunciation download pipeline.

Tests the flow: eligible candidates -> download -> verify stored paths.
Uses in-memory SQLite and mocked HTTP downloads.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.sqla_candidate_pronunciation_repository import (
    SqlaCandidatePronunciationRepository,
)
from backend.infrastructure.persistence.sqla_candidate_repository import (
    SqlaCandidateRepository,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session


def _insert_candidate(session: Session, candidate_id: int, lemma: str, source_id: int = 1) -> None:
    session.execute(text(
        "INSERT INTO candidates (id, source_id, lemma, pos, "
        "zipf_frequency, is_sweet_spot, context_fragment, fragment_purity, "
        "occurrences, status, is_phrasal_verb, has_custom_context_fragment) "
        f"VALUES ({candidate_id}, {source_id}, '{lemma}', 'NOUN', "
        f"4.0, 1, 'a {lemma}', 'clean', 1, 'learn', 0, 0)"
    ))


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

            # Step 1: verify eligibility
            eligible = pron_repo.get_eligible_candidate_ids(source_id=1)
            assert set(eligible) == {1, 2}

            # Step 2: run download use case
            pron_source = MagicMock()
            pron_source.get_audio_urls.return_value = (
                "https://cdn/us/hello.mp3",
                "https://cdn/uk/hello.mp3",
            )

            use_case = DownloadPronunciationUseCase(
                candidate_repo=candidate_repo,
                pronunciation_repo=pron_repo,
                pronunciation_source=pron_source,
                media_root=str(tmp_path),
            )

            with patch("backend.application.use_cases.download_pronunciation.download_file"):
                use_case.execute_one(1)

            session.commit()

            # Step 3: verify result
            result = pron_repo.get_by_candidate_id(1)
            assert result is not None
            assert result.us_audio_path is not None
            assert "1_pron_us.mp3" in result.us_audio_path
            assert result.uk_audio_path is not None
            assert "1_pron_uk.mp3" in result.uk_audio_path

            # Step 4: candidate 1 no longer eligible
            remaining = pron_repo.get_eligible_candidate_ids(source_id=1)
            assert 1 not in remaining

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
                media_root=str(tmp_path),
            )

            use_case.execute_one(1)
            session.commit()

            result = pron_repo.get_by_candidate_id(1)
            assert result is not None
            assert result.us_audio_path is None
            assert result.uk_audio_path is None
