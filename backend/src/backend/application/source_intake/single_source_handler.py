from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.source_intake.kind_handler import KindHandler
from backend.application.source_intake.source_draft import SourceDraft
from backend.domain.services.word_count import count_words
from backend.domain.value_objects.content import BookContent, SubtitlesContent

if TYPE_CHECKING:
    from backend.domain.value_objects.content import Content, Kind
    from backend.domain.value_objects.format import Format
    from backend.domain.value_objects.question import Answers, Question


class SingleSourceHandler(KindHandler):
    """Text, a song or subtitles become one source; subtitles keep their video."""

    def __init__(self, kind: Kind) -> None:
        self._kind = kind

    @property
    def kind(self) -> Kind:
        return self._kind

    def questions(self, content: Content) -> tuple[Question, ...]:
        return ()

    def drafts(
        self, content: Content, answers: Answers, source_format: Format, label: str,
    ) -> tuple[SourceDraft, ...]:
        assert not isinstance(content, BookContent)
        return (
            SourceDraft(
                document=content.document,
                kind=content.kind,
                source_format=source_format,
                own_title=content.title,
                label=label,
                words=count_words(content.document.text),
                video=content.video if isinstance(content, SubtitlesContent) else None,
            ),
        )
