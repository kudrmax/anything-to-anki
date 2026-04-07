from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.infrastructure.api.dependencies import get_session_factory
from backend.infrastructure.api.routes import anki, candidates, generation, known_words, prompts, settings, sources, stats
from backend.infrastructure.api.routes.media import router as media_router
from backend.infrastructure.persistence.database import (
    reconcile_media_files,
    reset_stuck_processing,
    resume_generation_jobs,
    resume_media_extraction_jobs,
    run_alembic_migrations,
    upgrade_schema,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    session_factory = get_session_factory()
    db_url = str(session_factory.kw["bind"].url)  # type: ignore[union-attr]
    if ":memory:" not in db_url:
        run_alembic_migrations(db_url)
    upgrade_schema(session_factory)  # type: ignore[arg-type]
    reset_stuck_processing(session_factory)  # type: ignore[arg-type]
    resume_generation_jobs(session_factory)  # type: ignore[arg-type]
    resume_media_extraction_jobs(session_factory)  # type: ignore[arg-type]
    media_root = os.environ.get("MEDIA_ROOT", os.path.join(os.getenv("DATA_DIR", "."), "media"))
    reconcile_media_files(session_factory, media_root)  # type: ignore[arg-type]
    yield


app = FastAPI(title="VocabMiner API", version="0.2.0", lifespan=lifespan)

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
app.include_router(prompts.router)
app.include_router(anki.router)
app.include_router(stats.router)
app.include_router(generation.router)

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
