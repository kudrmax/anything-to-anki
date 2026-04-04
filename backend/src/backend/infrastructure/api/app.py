from __future__ import annotations

from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.infrastructure.api.dependencies import get_session_factory
from backend.infrastructure.api.routes import candidates, known_words, settings, sources
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
