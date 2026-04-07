from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.media_dtos import CleanupMediaKind
from backend.application.dto.settings_dtos import SettingsDTO, UpdateSettingsRequest  # noqa: TC001
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.infrastructure.container import Container

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SettingsDTO:
    use_case = container.manage_settings_use_case(session)
    return use_case.get_settings()


@router.patch("")
def update_settings(
    request: UpdateSettingsRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> SettingsDTO:
    use_case = container.manage_settings_use_case(session)
    result = use_case.update_settings(request)
    session.commit()
    return result


@router.get("/media-stats")
def get_media_stats(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[dict[str, object]]:
    use_case = container.get_media_storage_stats_use_case(session)
    stats = use_case.execute()
    return [
        {
            "source_id": s.source_id,
            "source_title": s.source_title,
            "screenshot_bytes": s.screenshot_bytes,
            "audio_bytes": s.audio_bytes,
            "screenshot_count": s.screenshot_count,
            "audio_count": s.audio_count,
        }
        for s in stats
    ]


@router.post("/media-cleanup", status_code=204)
def cleanup_media(
    body: dict[str, object],
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> None:
    source_id_raw = body.get("source_id")
    kind_raw = body.get("kind")
    if not isinstance(source_id_raw, int) or not isinstance(kind_raw, str):
        raise HTTPException(status_code=400, detail="source_id (int) and kind (str) required")
    try:
        kind = CleanupMediaKind(kind_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid kind: {kind_raw}") from None

    use_case = container.cleanup_media_use_case(session)
    use_case.execute(source_id=source_id_raw, kind=kind)
    session.commit()
