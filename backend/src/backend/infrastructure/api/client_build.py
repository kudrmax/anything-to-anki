from __future__ import annotations

import re
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp

CLIENT_BUILD_HEADER = "X-Client-Build"
STALE_CLIENT_HEADER = "X-Client-Stale"
# Wipes the browser's copy of the page and bundle, so the next open loads the
# current build. It is the only way to reach a client built before it could reload itself.
CLEAR_CACHE = '"cache"'
_BUNDLE = re.compile(r'<script[^>]+src="/assets/([^"]+\.js)"')
_FETCH_DEST = "empty"


def bundle_name(index_html: str) -> str | None:
    """The entry bundle the page loads: it changes with every build."""
    match = _BUNDLE.search(index_html)
    return match.group(1) if match else None


class _BuildOnDisk:
    """The build the server hands out now: a rebuild while it runs changes it, and a page
    opened after the rebuild must not be told it is old."""

    def __init__(self, dist: Path) -> None:
        self._index = dist / "index.html"
        self._read_at: float | None = None
        self._build: str | None = None

    def get(self) -> str | None:
        modified = self._index.stat().st_mtime if self._index.is_file() else None
        if modified != self._read_at:
            self._read_at = modified
            self._build = bundle_name(self._index.read_text()) if modified is not None else None
        return self._build


class StaleClientMiddleware(BaseHTTPMiddleware):
    """Tells a page running an old build to reload, and clears its cached copy.

    Only fetch requests are checked: pictures and audio carry no build.
    """

    def __init__(self, app: ASGIApp, dist: Path) -> None:
        super().__init__(app)
        self._build = _BuildOnDisk(dist)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        if request.headers.get("Sec-Fetch-Dest") != _FETCH_DEST:
            return response
        build = self._build.get()
        if build is not None and request.headers.get(CLIENT_BUILD_HEADER) != build:
            response.headers["Clear-Site-Data"] = CLEAR_CACHE
            response.headers[STALE_CLIENT_HEADER] = "1"
        return response
