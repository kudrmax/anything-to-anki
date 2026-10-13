"""Subtitles as a document: one flowing paragraph of their lines, each with its subtitle's time."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.exceptions import InvalidSourceInputError
from backend.domain.value_objects.document import Document, Line, Paragraph, ParagraphMode
from backend.infrastructure.adapters.regex_srt_parser import SrtCue

if TYPE_CHECKING:
    from backend.infrastructure.adapters.regex_srt_parser import RegexSrtParser

def subtitles_document(srt_text: str, parser: RegexSrtParser) -> Document:
    lines = tuple(
        Line(text, start_ms=cue.start_ms, end_ms=cue.end_ms)
        for cue in _without_rolling_repeats(parser.parse_cues(srt_text))
        for text in cue.lines
    )
    if not lines:
        msg = "No subtitles to read"
        raise InvalidSourceInputError(msg)
    return Document(blocks=(Paragraph(lines=lines, mode=ParagraphMode.FLOW),))


def _without_rolling_repeats(cues: list[SrtCue]) -> list[SrtCue]:
    """YouTube's rolling captions start each subtitle with the last line of the one before."""
    kept: list[SrtCue] = []
    for cue in cues:
        lines = cue.lines
        if kept and lines and lines[0] == kept[-1].lines[-1]:
            lines = lines[1:]
        if lines:
            kept.append(SrtCue(start_ms=cue.start_ms, end_ms=cue.end_ms, lines=lines))
    return kept
