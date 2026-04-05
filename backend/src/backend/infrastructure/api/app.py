from __future__ import annotations

import os
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.infrastructure.api.dependencies import get_session_factory
from backend.infrastructure.api.routes import anki, candidates, known_words, settings, sources, stats
from backend.infrastructure.persistence.database import create_tables, reset_stuck_processing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    session_factory = get_session_factory()
    create_tables(session_factory)  # type: ignore[arg-type]
    reset_stuck_processing(session_factory)  # type: ignore[arg-type]
    yield


app = FastAPI(title="VocabMiner API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router)
app.include_router(candidates.router)
app.include_router(known_words.router)
app.include_router(settings.router)
app.include_router(anki.router)
app.include_router(stats.router)

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
