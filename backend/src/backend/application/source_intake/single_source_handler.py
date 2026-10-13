from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.dto.add_source_dtos import SourcesCreated
from backend.application.source_intake.kind_handler import KindHandler
from backend.domain.value_objects.content import BookContent, SubtitlesContent

if TYPE_CHECKING:
    from backend.application.source_intake.source_writer import SourceWriter
    from backend.domain.value_objects.content import Content, Kind
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.question import Answers, Question

logger = logging.getLogger(__name__)


class SingleSourceHandler(KindHandler):
    """Text, a song or subtitles become one source; subtitles keep their video."""

    def __init__(self, kind: Kind, writer: SourceWriter) -> None:
        self._kind = kind
        self._writer = writer

    @property
    def kind(self) -> Kind:
        return self._kind

    def questions(self, content: Content) -> tuple[Question, ...]:
        return ()

    def create(self, content: Content, answers: Answers, source_format: Format) -> SourcesCreated:
        assert not isinstance(content, BookContent)
        source_id = self._writer.write(
            document=content.document,
            title=content.title,
            source_format=source_format,
            kind=content.kind,
            video=content.video if isinstance(content, SubtitlesContent) else None,
        )
        logger.info(
            "Created %s source id=%s from %s title=%r",
            content.kind, source_id, source_format, content.title,
        )
        return SourcesCreated(source_ids=[source_id])
