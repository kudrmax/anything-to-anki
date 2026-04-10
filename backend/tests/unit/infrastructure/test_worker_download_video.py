from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
class TestDownloadYoutubeVideoJob:
    async def test_calls_use_case(self) -> None:
        from backend.infrastructure.workers import download_youtube_video

        mock_use_case = MagicMock()
        mock_session = MagicMock()
        mock_container = MagicMock()

        ctx_mgr = MagicMock()
        ctx_mgr.__enter__ = MagicMock(return_value=mock_session)
        ctx_mgr.__exit__ = MagicMock(return_value=False)
        mock_container.session_scope.return_value = ctx_mgr
        mock_container.download_video_use_case.return_value = mock_use_case

        await download_youtube_video({"container": mock_container}, source_id=42)

        mock_container.download_video_use_case.assert_called_once_with(mock_session)
        mock_use_case.execute.assert_called_once_with(42)

    async def test_marks_error_on_failure(self) -> None:
        from backend.infrastructure.workers import download_youtube_video

        mock_use_case = MagicMock()
        mock_use_case.execute.side_effect = Exception("download failed")

        # First session_scope call — for download_video_use_case
        # Second session_scope call — for SqlaSourceRepository.update_status
        session_1 = MagicMock()
        session_2 = MagicMock()

        call_count = [0]

        def make_ctx() -> MagicMock:
            ctx = MagicMock()
            idx = min(call_count[0], 1)
            ctx.__enter__ = MagicMock(return_value=[session_1, session_2][idx])
            ctx.__exit__ = MagicMock(return_value=False)
            call_count[0] += 1
            return ctx

        mock_container = MagicMock()
        mock_container.session_scope.side_effect = make_ctx
        mock_container.download_video_use_case.return_value = mock_use_case

        mock_repo = MagicMock()
        mock_source_repo_cls = MagicMock(return_value=mock_repo)

        import unittest.mock as _mock

        with _mock.patch(
            "backend.infrastructure.persistence.sqla_source_repository.SqlaSourceRepository",
            mock_source_repo_cls,
        ):
            # Should NOT raise — worker catches exceptions
            await download_youtube_video({"container": mock_container}, source_id=42)

        # Ensure two session_scope calls were made (one for use case, one for error handling)
        assert call_count[0] == 2
