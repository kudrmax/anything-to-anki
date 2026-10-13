"""Move sources made before documents onto documents.

Revision ID: 0045
Revises: 0044

Written for the data of this app's two copies (prod and dev) at the time of the move;
it reads only the database and imports nothing of the app. Once applied everywhere,
its body is emptied.

Old data keeps what the user sees: a processed source's document is its cleaned text
as it is, line by line, in one flowing paragraph per paragraph of the text; candidates
are not recreated, they only get the places of their phrase and target. A video's lines
get the time of their subtitle from its stored SRT. A source never processed is read
from its stored text: paragraphs apart by blank lines, a song line by line.
"""
from __future__ import annotations

import bisect
import difflib
import json
import re
from typing import Any

import sqlalchemy as sa
from alembic import op

Span = tuple[int, int]
Times = list[tuple[int, int] | None]

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

BLOCK_SEPARATOR = "\n\n"
FLOW_SEPARATOR = " "
LINES_SEPARATOR = "\n"
VIDEO_FORMATS = ("video_file", "youtube")


# --- subtitles, as the old pipeline parsed them -------------------------------------------
_BLOCK_SEP_RE = re.compile(r"\r?\n\r?\n")
_SEQ_NUM_RE = re.compile(r"^\d+$")
_SRT_TIMECODE_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}")
_POSITION_TAG_RE = re.compile(r"\{[^}]*\}")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_ANNOTATION_RE = re.compile(r"\[[^\[\]]*\]|\([^()]*\)")
_SPEAKER_LABEL_RE = re.compile(r"^([-–]\s*)?[A-Z][A-Z0-9'.]+(?: [A-Z0-9'.]+){0,3}:\s*")
_MULTI_SPACES_RE = re.compile(r"[ \t]{2,}")
_NO_WORDS_RE = re.compile(r"^[^\w]*$")
_CREDITS_RE = re.compile(r"(?i)(subtitles?\s+by|opensubtitles?|sync\s+by|corrected\s+by)")


def _ms(value: str) -> int:
    hms, ms = value.strip().split(",")
    h, m, s = hms.split(":")
    return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms)


def _srt_lines(raw: str) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    for block in _BLOCK_SEP_RE.split(raw):
        start = end = None
        text_lines: list[str] = []
        skip = False
        for line in block.splitlines():
            if _CREDITS_RE.search(line):
                skip = True
                break
            if _SEQ_NUM_RE.match(line.strip()):
                continue
            if _SRT_TIMECODE_RE.match(line.strip()):
                left, right = line.strip().split("-->")
                start, end = _ms(left), _ms(right.split()[0])
                continue
            text_lines.append(_HTML_TAG_RE.sub("", _POSITION_TAG_RE.sub("", line)))
        lines = []
        for line in _ANNOTATION_RE.sub("", "\n".join(text_lines)).splitlines():
            line = _SPEAKER_LABEL_RE.sub(r"\1", line.strip())
            line = _MULTI_SPACES_RE.sub(" ", line).strip()
            if not _NO_WORDS_RE.match(line):
                lines.append(line)
        if skip or not lines or start is None or end is None:
            continue
        result.extend((line, start, end) for line in lines)
    return result


def _times(lines: list[str], raw_srt: str) -> list[tuple[int, int] | None]:
    """Each line of the cleaned text gets the time of the subtitle it came from."""
    parsed = _srt_lines(raw_srt)
    times: list[tuple[int, int] | None] = [None] * len(lines)
    matcher = difflib.SequenceMatcher(None, [p[0] for p in parsed], lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
            for k in range(j2 - j1):
                times[j1 + k] = (parsed[i1 + k][1], parsed[i1 + k][2])
    return times


# --- documents ----------------------------------------------------------------------------
class _Layout:
    """The document joined as the parser and the screen see it, and the way back."""

    def __init__(self, blocks: list[tuple[list[str], str]]) -> None:
        self.starts: list[int] = []
        self.places: list[tuple[int, int, int]] = []  # (block, line, start)
        parts: list[str] = []
        offset = 0
        for b, (lines, separator) in enumerate(blocks):
            if b:
                parts.append(BLOCK_SEPARATOR)
                offset += len(BLOCK_SEPARATOR)
            for n, line in enumerate(lines):
                if n:
                    parts.append(separator)
                    offset += len(separator)
                self.places.append((b, n, offset))
                self.starts.append(offset)
                parts.append(line)
                offset += len(line)
        self.text = "".join(parts)

    def position(self, start: int, end: int) -> list[int] | None:
        first = self.places[bisect.bisect_right(self.starts, start) - 1]
        last = self.places[bisect.bisect_right(self.starts, max(end - 1, start)) - 1]
        if first[0] != last[0]:
            return None
        return [first[0], first[1], start - first[2], last[1], end - last[2]]

    def lines_between(self, start: int, end: int) -> list[int]:
        """Indexes of the layout lines a piece of text takes."""
        first = bisect.bisect_right(self.starts, start) - 1
        last = bisect.bisect_right(self.starts, max(end - 1, start)) - 1
        return list(range(first, last + 1))


def _paragraphs(text: str) -> list[list[str]]:
    return [
        [line.strip() for line in block.split("\n") if line.strip()]
        for block in re.split(r"\n\s*\n", text)
        if block.strip()
    ]


def _document(blocks: list[dict[str, Any]]) -> str:
    return json.dumps({"blocks": blocks}, ensure_ascii=False)


def _paragraph(lines: list[str], mode: str, times: Times | None) -> dict[str, Any]:
    return {
        "type": "paragraph",
        "mode": mode,
        "lines": [
            {"text": line, **({"start_ms": t[0], "end_ms": t[1]} if t else {})}
            for line, t in zip(lines, times or [None] * len(lines), strict=True)
        ],
    }


# --- places of phrases and targets, as the screen found them ------------------------------
_W = "[A-Za-z0-9_]"
_JS_B = f"(?:(?<={_W})(?!{_W})|(?<!{_W})(?={_W}))"


def _flex(phrase: str) -> str:
    return r"\s+".join(re.escape(word) for word in phrase.strip().split())


def _target_patterns(lemma: str, surface: str | None, phrasal: bool) -> list[re.Pattern[str]]:
    """The patterns the source screen highlighted the target with (lib/text/segments.ts)."""
    patterns = []
    words = lemma.split()
    if surface:
        patterns.append(re.compile(_flex(surface), re.IGNORECASE))
    elif len(words) == 1:
        patterns.append(re.compile(f"{_JS_B}{re.escape(lemma)}{_W}*", re.IGNORECASE))
    else:
        rest = r"\s+".join(re.escape(w) for w in words[1:])
        patterns.append(
            re.compile(f"{_JS_B}{re.escape(words[0])}{_W}*\\s+{rest}", re.IGNORECASE),
        )
    if phrasal and len(words) >= 2:
        rest = r"\s+".join(re.escape(w) for w in words[1:])
        verb = re.escape(words[0])
        patterns.append(re.compile(
            f"{_JS_B}{verb}{_W}*(?:\\s+\\S+){{0,3}}?\\s+{rest}{_JS_B}", re.IGNORECASE,
        ))
    return patterns


def _split_target(text: str, start: int, end: int, surface: str | None) -> Span | None:
    """A phrasal verb split by other words: from its first word to its last, in the phrase."""
    words = [w for w in (surface or "").split() if re.search(r"\w", w)]
    if len(words) < 2:
        return None
    first = re.compile(rf"(?<!\w){re.escape(words[0])}(?!\w)", re.IGNORECASE).search(
        text, start, end,
    )
    if first is None:
        return None
    last = None
    particle = rf"(?<!\w){re.escape(words[-1])}(?!\w)"
    for found in re.finditer(particle, text[first.end():end], re.IGNORECASE):
        last = found
    if last is None:
        return None
    return first.start(), first.end() + last.end()


def _target(
    text: str, phrase: Span, lemma: str, surface: str | None, phrasal: bool,
) -> Span | None:
    start, end = phrase
    for pattern in _target_patterns(lemma, surface, phrasal):
        inner = pattern.search(text, start, end)
        if inner:
            return inner.start(), inner.end()
    return _split_target(text, start, end, surface)


def _phrase(
    text: str, fragment: str, wanted_time: Span | None, layout: _Layout, times: Times | None,
) -> Span | None:
    """The first place of the phrase, or for a clip already cut, the place it was cut from."""
    if not fragment.strip():
        return None
    found = list(re.finditer(_flex(fragment), text, re.IGNORECASE))
    if not found:
        return None
    if wanted_time is not None and times is not None:
        for match in found:
            span = [times[i] for i in layout.lines_between(match.start(), match.end())]
            timed = [t for t in span if t is not None]
            if len(timed) == len(span) and _union(timed) == wanted_time:
                return match.start(), match.end()
    return found[0].start(), found[0].end()


def _union(times: list[tuple[int, int]]) -> Span:
    return min(t[0] for t in times), max(t[1] for t in times)


# --- the move -----------------------------------------------------------------------------
def upgrade() -> None:
    connection = op.get_bind()
    sources = connection.execute(sa.text(
        "SELECT id, format, kind, raw_text, cleaned_text FROM sources"
        " WHERE role = 'content'"
        " AND id NOT IN (SELECT source_id FROM source_documents)"
    )).all()
    for source_id, source_format, kind, raw_text, cleaned_text in sources:
        if cleaned_text is not None:
            _move_processed(connection, source_id, source_format, raw_text, cleaned_text)
        else:
            _move_unprocessed(connection, source_id, source_format, kind, raw_text)


def _move_processed(
    connection: sa.Connection, source_id: int, source_format: str, raw_text: str, cleaned: str,
) -> None:
    paragraphs = _paragraphs(cleaned)
    is_video = source_format in VIDEO_FORMATS
    all_lines = [line for paragraph in paragraphs for line in paragraph]
    line_times = _times(all_lines, raw_text) if is_video else None
    blocks, offset = [], 0
    for paragraph in paragraphs:
        times = line_times[offset:offset + len(paragraph)] if line_times else None
        blocks.append(_paragraph(paragraph, "flow", times))
        offset += len(paragraph)
    connection.execute(
        sa.text("INSERT INTO source_documents (source_id, document) VALUES (:id, :document)"),
        {"id": source_id, "document": _document(blocks)},
    )

    layout = _Layout([(paragraph, FLOW_SEPARATOR) for paragraph in paragraphs])
    candidates = connection.execute(sa.text(
        "SELECT c.id, c.context_fragment, c.lemma, c.surface_form, c.is_phrasal_verb,"
        " c.has_custom_context_fragment, m.start_ms, m.end_ms FROM candidates c"
        " LEFT JOIN candidate_media m ON m.candidate_id = c.id WHERE c.source_id = :id"
    ), {"id": source_id}).all()
    for cid, fragment, lemma, surface, phrasal, custom, start_ms, end_ms in candidates:
        if custom:
            continue
        wanted = (start_ms, end_ms) if start_ms is not None and end_ms is not None else None
        phrase = _phrase(layout.text, fragment, wanted, layout, line_times)
        if phrase is None:
            continue
        phrase_position = layout.position(*phrase)
        if phrase_position is None:
            continue
        target = _target(layout.text, phrase, lemma, surface, bool(phrasal))
        target_position = layout.position(*target) if target else None
        connection.execute(
            sa.text(
                "UPDATE candidates SET phrase_position = :phrase, target_position = :target"
                " WHERE id = :id"
            ),
            {
                "id": cid,
                "phrase": json.dumps(phrase_position),
                "target": json.dumps(target_position) if target_position else None,
            },
        )


def _move_unprocessed(
    connection: sa.Connection, source_id: int, source_format: str, kind: str, raw: str,
) -> None:
    if source_format not in ("plain", "epub"):
        msg = f"Source {source_id}: an unprocessed {source_format} source can't be moved"
        raise RuntimeError(msg)
    paragraphs = _paragraphs(raw)
    mode = "lines" if kind == "song" else "flow"
    blocks = [_paragraph(paragraph, mode, None) for paragraph in paragraphs]
    connection.execute(
        sa.text("INSERT INTO source_documents (source_id, document) VALUES (:id, :document)"),
        {"id": source_id, "document": _document(blocks)},
    )


# Sources made before documents still have their text; those made after don't.
_OLD_SOURCES = "SELECT id FROM sources WHERE role = 'content' AND raw_text != ''"


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text(
        "UPDATE candidates SET phrase_position = NULL, target_position = NULL"
        f" WHERE source_id IN ({_OLD_SOURCES})"
    ))
    connection.execute(
        sa.text(f"DELETE FROM source_documents WHERE source_id IN ({_OLD_SOURCES})"),
    )
