from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from backend.infrastructure.api.dependencies import (
    get_container,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:

    from backend.infrastructure.container import Container

router = APIRouter(tags=["media"])


@router.get("/media/{source_id}/{filename}")
async def serve_media_file(
    source_id: int,
    filename: str,
    container: Container = Depends(get_container),  # noqa: B008
) -> FileResponse:
    media_root = container.media_root()
    file_path = os.path.join(media_root, str(source_id), filename)
    if not os.path.exists(file_path):
        await container.lazy_media_reconciler().schedule(source_id, filename)
        raise HTTPException(status_code=404, detail="Media file not found")
    return FileResponse(file_path)
