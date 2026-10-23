from __future__ import annotations

import os
import time
import traceback
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.domain.exceptions import LongOperationInProgressError
from backend.infrastructure.api.client_build import StaleClientMiddleware
from backend.infrastructure.api.dependencies import get_container, get_session_factory
from backend.infrastructure.api.routes import (
    anki,
    bootstrap,
    card_reports,
    collections,
    export,
    generation,
    known_words,
    long_operation,
    operations,
    phrases,
    review,
    settings,
    sources,
    stats,
    unknown_words,
    usage,
    vocabulary,
    words,
)
from backend.infrastructure.api.routes.media import router as media_router
from backend.infrastructure.api.routes.queue import router as queue_router
from backend.infrastructure.logging_setup import configure_logging
from backend.infrastructure.persistence.database import (
    cleanup_parse_cache,
    reconcile_media_files,
    release_long_operation_lock,
    release_source_operations,
    run_alembic_migrations,
)
from backend.infrastructure.startup_heap import freeze_startup_heap

if TYPE_CHECKING:
    from starlette.responses import Response

configure_logging("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    session_factory = get_session_factory()
    db_url = str(session_factory.kw["bind"].url)

    if ":memory:" not in db_url:
        run_alembic_migrations(db_url)
    release_source_operations(session_factory)
    release_long_operation_lock(session_factory)
    cleanup_parse_cache(session_factory)
    data_dir = os.path.abspath(os.getenv("DATA_DIR", "./data"))
    media_root = os.environ.get("MEDIA_ROOT", os.path.join(data_dir, "media"))
    reconcile_media_files(session_factory, media_root)
    _rebuild_card_states()
    freeze_startup_heap()
    yield
    get_container().close_background_work()


def _rebuild_card_states() -> None:
    """The stored card state is computed anew before the first request: the rules or the
    tables may have changed since the last run."""
    started = time.perf_counter()
    get_container().rebuild_card_states()
    _log.info("Card states rebuilt", seconds=round(time.perf_counter() - started, 2))


app = FastAPI(title="AnythingToAnki API", version="0.2.0", lifespan=lifespan)

_log = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        method = request.method
        path = request.url.path
        try:
            response = await call_next(request)
        except Exception:
            _log.error(
                "Unhandled exception",
                method=method,
                path=path,
                traceback=traceback.format_exc(),
            )
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

        if response.status_code >= 400:
            _log.warning(
                "Error response",
                method=method,
                path=path,
                status=response.status_code,
            )
        return response


# One code for every write refused while a long operation runs: the frontend shows the
# operation instead of an error.
LONG_OPERATION_IN_PROGRESS_STATUS = 423


@app.exception_handler(LongOperationInProgressError)
async def long_operation_in_progress(
    _request: Request, exc: LongOperationInProgressError,
) -> JSONResponse:
    return JSONResponse(
        status_code=LONG_OPERATION_IN_PROGRESS_STATUS, content={"detail": str(exc)},
    )


app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router)
app.include_router(review.router)
app.include_router(operations.router)
app.include_router(media_router)
app.include_router(words.router)
app.include_router(phrases.router)
app.include_router(card_reports.router)
app.include_router(known_words.router)
app.include_router(unknown_words.router)
app.include_router(vocabulary.router)
app.include_router(settings.router)
app.include_router(long_operation.router)
app.include_router(anki.router)
app.include_router(export.router)
app.include_router(stats.router)
app.include_router(usage.router)
app.include_router(generation.router)
app.include_router(queue_router)
app.include_router(collections.router)
app.include_router(bootstrap.router)

# Browsers must re-check the page on every open: it names the bundle of the
# current build, and a cached copy keeps an old frontend alive after a deploy.
INDEX_CACHE_CONTROL = "no-cache"


def index_response(dist: Path) -> FileResponse:
    return FileResponse(str(dist / "index.html"), headers={"Cache-Control": INDEX_CACHE_CONTROL})


_dist_env = os.getenv("FRONTEND_DIST")
_DIST = Path(_dist_env) if _dist_env else Path(__file__).parents[5] / "frontends" / "web" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="static-assets")
    app.add_middleware(StaleClientMiddleware, dist=_DIST)

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:  # noqa: RUF029
        candidate = _DIST / full_path
        if candidate.is_file() and candidate.name != "index.html":
            return FileResponse(str(candidate))
        return index_response(_DIST)
