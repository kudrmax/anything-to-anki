from __future__ import annotations

import os
import traceback
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from backend.infrastructure.api.dependencies import get_session_factory
from backend.infrastructure.api.routes import (
    anki,
    candidates,
    collections,
    export,
    generation,
    known_words,
    settings,
    sources,
    stats,
)
from backend.infrastructure.api.routes.media import router as media_router
from backend.infrastructure.api.routes.queue import router as queue_router
from backend.infrastructure.api.routes.pronunciation import router as pronunciation_router
from backend.infrastructure.api.routes.tts import router as tts_router
from backend.infrastructure.logging_setup import configure_logging
from backend.infrastructure.persistence.database import (
    reconcile_media_files,
    reset_stuck_processing,
    run_alembic_migrations,
)

configure_logging("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    session_factory = get_session_factory()
    db_url = str(session_factory.kw["bind"].url)

    if ":memory:" not in db_url:
        run_alembic_migrations(db_url)
    reset_stuck_processing(session_factory)
    data_dir = os.path.abspath(os.getenv("DATA_DIR", "./data"))
    media_root = os.environ.get("MEDIA_ROOT", os.path.join(data_dir, "media"))
    reconcile_media_files(session_factory, media_root)
    yield


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


app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router)
app.include_router(media_router)
app.include_router(candidates.router)
app.include_router(known_words.router)
app.include_router(settings.router)
app.include_router(anki.router)
app.include_router(export.router)
app.include_router(stats.router)
app.include_router(generation.router)
app.include_router(pronunciation_router)
app.include_router(tts_router)
app.include_router(queue_router)
app.include_router(collections.router)

_dist_env = os.getenv("FRONTEND_DIST")
_DIST = Path(_dist_env) if _dist_env else Path(__file__).parents[5] / "frontends" / "web" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:  # noqa: RUF029
        candidate = _DIST / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_DIST / "index.html"))
