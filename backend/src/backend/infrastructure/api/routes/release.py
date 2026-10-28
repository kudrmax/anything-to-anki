from __future__ import annotations

import mimetypes
import re
from datetime import date  # noqa: TC003 — pydantic resolves field types at runtime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Response
from markdown_it import MarkdownIt
from pydantic import BaseModel

from backend.application.dto.release_dtos import (  # noqa: TC001
    ChangelogEntryDTO,
    UpdateStateDTO,
    UpdateStatusDTO,
)
from backend.domain.exceptions import UpdateAlreadyRunningError
from backend.domain.value_objects.app_version import AppVersion
from backend.infrastructure.api.dependencies import get_container, use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.check_for_updates import CheckForUpdatesUseCase
    from backend.application.use_cases.get_changelog import GetChangelogUseCase
    from backend.application.use_cases.get_update_state import GetUpdateStateUseCase
    from backend.application.use_cases.start_update import StartUpdateUseCase

router = APIRouter(prefix="/api", tags=["release"])

ASSETS_URL = "/api/changelog/assets"
# A changelog image as the markdown names it, by its repository path.
IMAGE_SRC = re.compile(r'src="(docs/images/changelog/(\d+\.\d+\.\d+)/[^"]*)"')
_markdown = MarkdownIt("commonmark", {"html": False})


class VersionView(BaseModel):
    version: str


class ChangelogSectionView(BaseModel):
    title: str
    html: str


class ChangelogEntryView(BaseModel):
    version: str
    released_on: date
    summary: str
    sections: list[ChangelogSectionView]


class UpdateStatusView(BaseModel):
    current: str
    latest: str | None
    available: bool
    entries: list[ChangelogEntryView]
    check_failed: bool


def _html(body_markdown: str) -> str:
    rendered = _markdown.render(body_markdown)
    return IMAGE_SRC.sub(rf'src="{ASSETS_URL}/\2/\1"', rendered)


def _entry_view(entry: ChangelogEntryDTO) -> ChangelogEntryView:
    return ChangelogEntryView(
        version=entry.version,
        released_on=entry.released_on,
        summary=entry.summary,
        sections=[
            ChangelogSectionView(title=section.title, html=_html(section.body_markdown))
            for section in entry.sections
        ],
    )


@router.get("/version")
def get_version(container: Container = Depends(get_container)) -> VersionView:  # noqa: B008
    return VersionView(version=str(container.installed_release().version()))


@router.get("/updates")
def check_for_updates(
    force: bool = False,
    updates: CheckForUpdatesUseCase = Depends(  # noqa: B008
        use_case(Container.check_for_updates_use_case),  # noqa: B008
    ),
) -> UpdateStatusView:
    status: UpdateStatusDTO = updates.execute(force=force)
    return UpdateStatusView(
        current=status.current,
        latest=status.latest,
        available=status.available,
        entries=[_entry_view(entry) for entry in status.entries],
        check_failed=status.check_failed,
    )


@router.post("/update", status_code=202)
def start_update(
    update: StartUpdateUseCase = Depends(  # noqa: B008
        use_case(Container.start_update_use_case),  # noqa: B008
    ),
) -> None:
    try:
        update.execute()
    except UpdateAlreadyRunningError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/update/state")
def get_update_state(
    container: Container = Depends(get_container),  # noqa: B008
) -> UpdateStateDTO:
    state: GetUpdateStateUseCase = container.get_update_state_use_case()
    return state.execute()


@router.get("/changelog")
def get_changelog(
    changelog: GetChangelogUseCase = Depends(  # noqa: B008
        use_case(Container.get_changelog_use_case),  # noqa: B008
    ),
) -> list[ChangelogEntryView]:
    return [_entry_view(entry) for entry in changelog.all()]


@router.get("/changelog/unseen")
def get_unseen_changelog(
    changelog: GetChangelogUseCase = Depends(  # noqa: B008
        use_case(Container.get_changelog_use_case),  # noqa: B008
    ),
) -> list[ChangelogEntryView]:
    return [_entry_view(entry) for entry in changelog.unseen()]


@router.post("/changelog/seen", status_code=204)
def mark_changelog_seen(
    changelog: GetChangelogUseCase = Depends(  # noqa: B008
        use_case(Container.get_changelog_use_case),  # noqa: B008
    ),
) -> None:
    changelog.mark_seen()


@router.get("/changelog/assets/{version}/{path:path}")
def get_changelog_asset(
    version: str,
    path: str,
    container: Container = Depends(get_container),  # noqa: B008
) -> Response:
    try:
        requested = AppVersion.parse(version)
    except ValueError as error:
        raise HTTPException(status_code=404, detail="No such image") from error
    installed = container.installed_release()
    if requested == installed.version():
        content = installed.asset(path)
    else:
        content = container.release_source().asset(requested, path)
    if content is None:
        raise HTTPException(status_code=404, detail="No such image")
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type)
