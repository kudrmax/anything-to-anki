from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.media_dtos import CleanupMediaKind
from backend.application.dto.settings_dtos import (  # noqa: TC001
    FrequentWordThresholdDTO,
    SettingsDTO,
    UpdateSettingsRequest,
)
from backend.domain.exceptions import SourceOperationBusyError
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.cleanup_media import CleanupMediaUseCase
    from backend.application.use_cases.get_media_storage_stats import GetMediaStorageStatsUseCase
    from backend.application.use_cases.manage_settings import ManageSettingsUseCase

# NOTE: prefix is `/api/settings`, not `/settings`, because the frontend SPA
# has a `/settings` route — when the user refreshes that page, the browser
# does a full GET /settings, and if the API occupies that path they'd see
# the raw JSON instead of the app. Keep API endpoints under `/api/*` to
# avoid collisions with React Router routes.
router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(
    settings: ManageSettingsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_settings_use_case),  # noqa: B008
    ),
) -> SettingsDTO:
    return settings.get_settings()


@router.patch("")
def update_settings(
    request: UpdateSettingsRequest,
    settings: ManageSettingsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_settings_use_case),  # noqa: B008
    ),
) -> SettingsDTO:
    try:
        return settings.update_settings(request)
    except SourceOperationBusyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/frequent-word-thresholds")
def get_frequent_word_thresholds(
    settings: ManageSettingsUseCase = Depends(  # noqa: B008
        use_case(Container.manage_settings_use_case),  # noqa: B008
    ),
) -> list[FrequentWordThresholdDTO]:
    return settings.frequent_word_threshold_options()


@router.get("/media-stats")
def get_media_stats(
    media_stats: GetMediaStorageStatsUseCase = Depends(  # noqa: B008
        use_case(Container.get_media_storage_stats_use_case),  # noqa: B008
    ),
) -> list[dict[str, object]]:
    stats = media_stats.execute()
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
    cleanup: CleanupMediaUseCase = Depends(  # noqa: B008
        use_case(Container.cleanup_media_use_case),  # noqa: B008
    ),
) -> None:
    source_id_raw = body.get("source_id")
    kind_raw = body.get("kind")
    if not isinstance(source_id_raw, int) or not isinstance(kind_raw, str):
        raise HTTPException(status_code=400, detail="source_id (int) and kind (str) required")
    try:
        kind = CleanupMediaKind(kind_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid kind: {kind_raw}") from None

    cleanup.execute(source_id=source_id_raw, kind=kind)
