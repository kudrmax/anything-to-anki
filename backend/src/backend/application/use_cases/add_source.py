from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.application.dto.add_source_dtos import QuestionDTO, QuestionsRequired
from backend.application.source_intake.document_normalizer import EMPTY_SOURCE_MESSAGE
from backend.application.utils.typed_path import normalize_typed_path
from backend.domain.exceptions import InvalidAnswerError, InvalidSourceInputError
from backend.domain.value_objects.format import Format
from backend.domain.value_objects.question import Answers
from backend.domain.value_objects.source_input import LocalFile, PastedText

if TYPE_CHECKING:
    from collections.abc import Iterable

    from backend.application.dto.add_source_dtos import SourcesCreated
    from backend.application.source_intake.document_normalizer import DocumentNormalizer
    from backend.application.source_intake.kind_handler import KindHandler
    from backend.domain.ports.file_reader import FileReader
    from backend.domain.ports.format_detector import FormatDetector
    from backend.domain.ports.format_reader import FormatReader
    from backend.domain.value_objects.content import Content, Kind
    from backend.domain.value_objects.question import Question
    from backend.domain.value_objects.source_input import SourceInput

logger = logging.getLogger(__name__)

SUBTITLES_NEED_VIDEO_MESSAGE = "A .srt file can only be attached to a video"


class AddSourceUseCase:
    """Turns pasted text, a file or a link into sources.

    The reader of the input's format reads it into content, the handler of the content's
    kind makes the sources. Whatever either needs the user to choose comes back as questions;
    the next call brings every answer so far and starts over.
    """

    def __init__(
        self,
        detector: FormatDetector,
        readers: Iterable[FormatReader],
        handlers: Iterable[KindHandler],
        normalizer: DocumentNormalizer,
        file_reader: FileReader,
    ) -> None:
        self._detector = detector
        self._readers: dict[Format, FormatReader] = {reader.format: reader for reader in readers}
        self._handlers: dict[Kind, KindHandler] = {handler.kind: handler for handler in handlers}
        self._normalizer = normalizer
        self._file_reader = file_reader

    def execute(
        self,
        source_input: SourceInput,
        title: str | None = None,
        answers: Answers | None = None,
    ) -> QuestionsRequired | SourcesCreated:
        answers = answers or Answers()
        source_input = self._checked_input(source_input)
        source_format = self._detector.detect(source_input)
        attaches_subtitles = (
            isinstance(source_input, LocalFile) and source_input.subtitles_path is not None
        )
        if attaches_subtitles and source_format is not Format.VIDEO_FILE:
            raise InvalidSourceInputError(SUBTITLES_NEED_VIDEO_MESSAGE)

        reader = self._readers[source_format]
        asked = list(reader.questions(source_input))
        if pending := _pending(asked, answers):
            return pending
        content = self._normalizer.normalize(reader.read(source_input, answers))
        if title and title.strip():
            content = _titled(content, title.strip())

        handler = self._handlers[content.kind]
        asked += handler.questions(content)
        if pending := _pending(asked, answers):
            return pending
        _reject_unasked(asked, answers)
        return handler.create(content, answers, source_format)

    def _checked_input(self, source_input: SourceInput) -> SourceInput:
        match source_input:
            case PastedText():
                if not source_input.text.strip():
                    raise InvalidSourceInputError(EMPTY_SOURCE_MESSAGE)
            case LocalFile():
                source_input = LocalFile(
                    path=normalize_typed_path(source_input.path),
                    subtitles_path=(
                        normalize_typed_path(source_input.subtitles_path)
                        if source_input.subtitles_path
                        else None
                    ),
                )
                if not self._file_reader.exists(source_input.path):
                    msg = f"File not found: {source_input.path}"
                    raise FileNotFoundError(msg)
        return source_input


def _pending(asked: list[Question], answers: Answers) -> QuestionsRequired | None:
    for question in asked:
        answer = answers.get(question.id)
        if answer is not None and answer not in question.option_ids:
            msg = f"{answer!r} is not an option of {question.id!r}"
            raise InvalidAnswerError(msg)
    unanswered = [question for question in asked if not answers.has(question.id)]
    if not unanswered:
        return None
    return QuestionsRequired(questions=[QuestionDTO.from_question(q) for q in unanswered])


def _reject_unasked(asked: list[Question], answers: Answers) -> None:
    unasked = set(answers.chosen) - {question.id for question in asked}
    if unasked:
        msg = f"Answers to questions that weren't asked: {', '.join(sorted(unasked))}"
        raise InvalidAnswerError(msg)


def _titled(content: Content, title: str) -> Content:
    return replace(content, title=title)
