from __future__ import annotations

import re

from backend.domain.ports.source_parser import SourceParser
from backend.domain.ports.structured_srt_parser import StructuredSrtParser
from backend.domain.value_objects.parsed_srt import ParsedSrt
from backend.domain.value_objects.subtitle_block import SubtitleBlock

# Block separator (both Unix and Windows line endings)
_BLOCK_SEP_RE = re.compile(r"\r?\n\r?\n")

# Sequence number line: only digits
_SEQ_NUM_RE = re.compile(r"^\d+$")

# SRT timecode: 00:00:00,000 --> 00:00:00,000
_SRT_TIMECODE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}"
)

# Positional tags like {\an8}
_POSITION_TAG_RE = re.compile(r"\{[^}]*\}")

# HTML tags (remove tags, keep content)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# SDH annotations — sound descriptions and speaker names: [sighs], (MUSIC PLAYING),
# [Angstrom Levy]. Applied to the whole block, so an annotation may span lines.
_ANNOTATION_RE = re.compile(r"\[[^\[\]]*\]|\([^()]*\)")

# Speaker labels at start of line, after an optional dialogue dash: "JOE: ", "- BLACK SAMSON: "
_SPEAKER_LABEL_RE = re.compile(r"^([-–]\s*)?[A-Z][A-Z0-9'.]+(?: [A-Z0-9'.]+){0,3}:\s*")

_MULTI_SPACES_RE = re.compile(r"[ \t]{2,}")

# A line with nothing to read left, e.g. a dialogue dash whose annotation was removed
_NO_WORDS_RE = re.compile(r"^[^\w]*$")

# Credits patterns
_CREDITS_RE = re.compile(
    r"(?i)(subtitles?\s+by|opensubtitles?|sync\s+by|corrected\s+by)"
)


def _srt_time_to_ms(time_str: str) -> int:
    """Convert SRT timestamp "HH:MM:SS,mmm" to milliseconds."""
    time_str = time_str.strip()
    hms, ms_part = time_str.split(",")
    h, m, s = hms.split(":")
    return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms_part)


class RegexSrtParser(SourceParser, StructuredSrtParser):
    """Parses SRT subtitle format into plain text."""

    def parse(self, raw_text: str) -> str:
        """Convert SRT format to plain text (backward-compatible)."""
        return self.parse_structured(raw_text).text

    def parse_structured(self, raw_text: str) -> ParsedSrt:
        """Parse SRT into cleaned text + per-block char offsets and timecodes."""
        blocks_raw = _BLOCK_SEP_RE.split(raw_text)
        cleaned_text = ""
        blocks: list[SubtitleBlock] = []

        for block in blocks_raw:
            lines = block.splitlines()
            start_ms: int | None = None
            end_ms: int | None = None
            text_lines: list[str] = []
            skip_block = False

            for line in lines:
                if _CREDITS_RE.search(line):
                    skip_block = True
                    break

                if _SEQ_NUM_RE.match(line.strip()):
                    continue

                m = _SRT_TIMECODE_RE.match(line.strip())
                if m:
                    parts = line.strip().split("-->")
                    start_ms = _srt_time_to_ms(parts[0])
                    end_ms = _srt_time_to_ms(parts[1].split()[0])
                    continue

                line = _POSITION_TAG_RE.sub("", line)
                line = _HTML_TAG_RE.sub("", line)
                text_lines.append(line)

            block_lines = self._strip_annotations(text_lines)

            if skip_block or not block_lines or start_ms is None or end_ms is None:
                continue

            cleaned_block = "\n".join(block_lines)
            char_start = len(cleaned_text)
            cleaned_text += cleaned_block + "\n"
            char_end = len(cleaned_text)
            blocks.append(SubtitleBlock(
                start_ms=start_ms,
                end_ms=end_ms,
                char_start=char_start,
                char_end=char_end,
            ))

        final_text = cleaned_text.rstrip("\n")
        if blocks:
            last = blocks[-1]
            blocks[-1] = SubtitleBlock(
                start_ms=last.start_ms,
                end_ms=last.end_ms,
                char_start=last.char_start,
                char_end=min(last.char_end, len(final_text)),
            )
        return ParsedSrt(text=final_text, blocks=tuple(blocks))

    @staticmethod
    def _strip_annotations(text_lines: list[str]) -> list[str]:
        text = _ANNOTATION_RE.sub("", "\n".join(text_lines))
        result: list[str] = []
        for line in text.splitlines():
            line = _SPEAKER_LABEL_RE.sub(r"\1", line.strip())
            line = _MULTI_SPACES_RE.sub(" ", line).strip()
            if not _NO_WORDS_RE.match(line):
                result.append(line)
        return result
