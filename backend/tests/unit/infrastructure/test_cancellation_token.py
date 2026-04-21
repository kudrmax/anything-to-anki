from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.domain.exceptions import CancelledByUser
from backend.infrastructure.queue.cancellation_token import CancellationToken


@pytest.mark.unit
class TestCancellationToken:
    def test_check_passes_when_job_exists(self) -> None:
        job_repo = MagicMock()
        job_repo.job_exists.return_value = True
        token = CancellationToken(job_id=42, job_repo=job_repo)
        token.check()  # should not raise
        job_repo.job_exists.assert_called_once_with(42)

    def test_check_raises_when_job_deleted(self) -> None:
        job_repo = MagicMock()
        job_repo.job_exists.return_value = False
        token = CancellationToken(job_id=42, job_repo=job_repo)
        with pytest.raises(CancelledByUser, match="42"):
            token.check()

    def test_is_cancelled_returns_bool(self) -> None:
        job_repo = MagicMock()
        job_repo.job_exists.return_value = True
        token = CancellationToken(job_id=42, job_repo=job_repo)
        assert token.is_cancelled is False

        job_repo.job_exists.return_value = False
        assert token.is_cancelled is True
