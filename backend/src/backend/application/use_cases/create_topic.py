from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.entities.source import Source
from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.source_role import SourceRole
from backend.domain.value_objects.source_status import SourceStatus

if TYPE_CHECKING:
    from backend.domain.ports.source_repository import SourceRepository

logger = logging.getLogger(__name__)

DEFAULT_TITLE_LENGTH = 100
EMPTY_TOPIC_MESSAGE = "Topic cannot be empty"


class CreateTopicUseCase:
    """A topic: targets are generated for the query, phrases are found in other sources."""

    def __init__(self, source_repo: SourceRepository) -> None:
        self._source_repo = source_repo

    def execute(self, query: str, title: str | None = None) -> Source:
        if not query.strip():
            raise InvalidSourceInputError(EMPTY_TOPIC_MESSAGE)
        source = self._source_repo.create(
            Source(
                status=SourceStatus.NEW,
                title=(title or "").strip() or query[:DEFAULT_TITLE_LENGTH],
                role=SourceRole.TOPIC,
                topic_query=query,
            )
        )
        logger.info("Created topic source id=%s query=%r", source.id, query)
        return source
