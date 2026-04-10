from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.entities.source import Source
from backend.domain.exceptions import UnsupportedUrlError
from backend.domain.value_objects.content_type import resolve_content_type
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.ports.url_source_fetcher import UrlSourceFetcher

logger = logging.getLogger(__name__)


class CreateSourceFromUrlUseCase:
    """Creates a source from a URL (YouTube, etc.)."""

    def __init__(
        self,
        source_repo: SourceRepository,
        fetchers: list[UrlSourceFetcher],
    ) -> None:
        self._source_repo = source_repo
        self._fetchers = fetchers

    def _resolve_fetcher(self, url: str) -> UrlSourceFetcher:
        for fetcher in self._fetchers:
            if fetcher.can_handle(url):
                return fetcher
        raise UnsupportedUrlError(f"No fetcher for URL: {url}")

    def execute(
        self,
        url: str,
        title_override: str | None = None,
    ) -> Source:
        fetcher = self._resolve_fetcher(url)
        result = fetcher.fetch_subtitles(url)

        title = (title_override.strip() if title_override and title_override.strip() else None) or result.title
        content_type = resolve_content_type(result.input_method)

        source = Source(
            raw_text=result.srt_text,
            status=SourceStatus.NEW,
            input_method=result.input_method,
            content_type=content_type,
            source_url=url,
            title=title,
        )
        created = self._source_repo.create(source)
        logger.info(
            "Created URL source id=%s input_method=%s title=%r",
            created.id, created.input_method, title,
        )
        return created
