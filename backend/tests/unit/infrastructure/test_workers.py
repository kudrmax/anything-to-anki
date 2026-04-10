"""Tests for ARQ worker job functions.

The critical contract these tests encode:
**the worker must NEVER re-raise AI/media errors**. Letting a plain Exception
bubble out of an ARQ job in arq 0.27 just hard-fails the job and drops it
from Redis, leaving the DB row stuck in RUNNING forever. So the worker
catches everything and marks the row FAILED itself.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from backend.domain.exceptions import (
    AIServiceError,
    PermanentAIError,
    PermanentMediaError,
)
from backend.infrastructure.workers import (
    extract_media_for_candidate,
    generate_meanings_batch,
    shutdown,
    startup,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


def _make_container(
    meaning_repo: MagicMock | None = None,
    media_repo: MagicMock | None = None,
    meaning_use_case: MagicMock | None = None,
    media_use_case: MagicMock | None = None,
) -> MagicMock:
    """Build a mock Container whose session_scope yields a dummy session."""
    container = MagicMock()

    @contextmanager
    def _scope() -> Iterator[MagicMock]:
        yield MagicMock(name="session")

    container.session_scope.side_effect = _scope
    container.candidate_meaning_repository.return_value = meaning_repo or MagicMock()
    container.candidate_media_repository.return_value = media_repo or MagicMock()
    container.meaning_generation_use_case.return_value = (
        meaning_use_case or MagicMock()
    )
    container.media_extraction_use_case.return_value = media_use_case or MagicMock()
    return container


# --- generate_meanings_batch ------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_meanings_batch_happy_path_marks_running_only() -> None:
    """On success, worker marks RUNNING and lets the use case write DONE.
    mark_batch_failed must NOT be called."""
    meaning_repo = MagicMock()
    use_case = MagicMock()
    container = _make_container(meaning_repo=meaning_repo, meaning_use_case=use_case)

    await generate_meanings_batch({"container": container}, [1, 2, 3])

    assert meaning_repo.mark_running.call_count == 3
    use_case.execute_batch.assert_called_once_with([1, 2, 3])
    meaning_repo.mark_batch_failed.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_meanings_batch_on_ai_error_marks_failed_and_does_not_raise(
) -> None:
    """AIServiceError (HTTP 500 from ai_proxy, network, etc) must be caught:
    mark_batch_failed is called with error text, and the coroutine returns
    normally (no re-raise). This is the regression guard for the bug where
    the worker raised expecting ARQ to retry — which ARQ 0.27 does not do
    for plain Exceptions, leaving rows stuck in RUNNING."""
    meaning_repo = MagicMock()
    use_case = MagicMock()
    use_case.execute_batch.side_effect = AIServiceError("AI proxy error: 500")
    container = _make_container(meaning_repo=meaning_repo, meaning_use_case=use_case)

    await generate_meanings_batch({"container": container}, [10, 20])

    meaning_repo.mark_batch_failed.assert_called_once()
    ids_arg, err_arg = meaning_repo.mark_batch_failed.call_args.args
    assert ids_arg == [10, 20]
    assert "AIServiceError" in err_arg
    assert "AI proxy error: 500" in err_arg


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_meanings_batch_on_permanent_error_marks_failed() -> None:
    meaning_repo = MagicMock()
    use_case = MagicMock()
    use_case.execute_batch.side_effect = PermanentAIError("blocked by safety")
    container = _make_container(meaning_repo=meaning_repo, meaning_use_case=use_case)

    await generate_meanings_batch({"container": container}, [5])

    meaning_repo.mark_batch_failed.assert_called_once_with([5], "blocked by safety")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_meanings_batch_on_unexpected_error_marks_failed() -> None:
    """Even an unexpected exception (e.g. SQL integrity, KeyError) must be
    caught so the batch never gets stuck in RUNNING."""
    meaning_repo = MagicMock()
    use_case = MagicMock()
    use_case.execute_batch.side_effect = RuntimeError("boom")
    container = _make_container(meaning_repo=meaning_repo, meaning_use_case=use_case)

    await generate_meanings_batch({"container": container}, [7])

    meaning_repo.mark_batch_failed.assert_called_once()
    _, err_arg = meaning_repo.mark_batch_failed.call_args.args
    assert "RuntimeError" in err_arg
    assert "boom" in err_arg


# --- extract_media_for_candidate --------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_media_happy_path() -> None:
    media_repo = MagicMock()
    use_case = MagicMock()
    container = _make_container(media_repo=media_repo, media_use_case=use_case)

    await extract_media_for_candidate({"container": container}, 42)

    media_repo.mark_running.assert_called_once_with(42)
    use_case.execute_one.assert_called_once_with(42)
    media_repo.mark_failed.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_media_on_permanent_error_marks_failed() -> None:
    media_repo = MagicMock()
    use_case = MagicMock()
    use_case.execute_one.side_effect = PermanentMediaError("no subtitle window")
    container = _make_container(media_repo=media_repo, media_use_case=use_case)

    await extract_media_for_candidate({"container": container}, 42)

    media_repo.mark_failed.assert_called_once_with(42, "no subtitle window")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_extract_media_on_unexpected_error_marks_failed() -> None:
    media_repo = MagicMock()
    use_case = MagicMock()
    use_case.execute_one.side_effect = OSError("ffmpeg crashed")
    container = _make_container(media_repo=media_repo, media_use_case=use_case)

    await extract_media_for_candidate({"container": container}, 42)

    media_repo.mark_failed.assert_called_once()
    _, err_arg = media_repo.mark_failed.call_args.args
    assert "OSError" in err_arg
    assert "ffmpeg crashed" in err_arg


# --- startup / shutdown ------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_startup_installs_container_in_ctx() -> None:
    """ARQ calls on_startup once at worker boot. We patch Container to
    avoid pulling in the full DI graph (which would need spaCy, redis, etc)."""
    ctx: dict[str, object] = {}
    sentinel = MagicMock(name="container_instance")
    with patch(
        "backend.infrastructure.workers.Container", return_value=sentinel
    ) as ctor:
        await startup(ctx)
    ctor.assert_called_once_with()
    assert ctx["container"] is sentinel


@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_runs_without_error() -> None:
    """ARQ calls on_shutdown at worker exit. It just logs — make sure no
    exception is raised even when ctx is empty or missing ``container``."""
    await shutdown({})
    await shutdown({"container": MagicMock()})
