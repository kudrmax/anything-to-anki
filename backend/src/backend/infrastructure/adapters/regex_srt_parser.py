from __future__ import annotations

import re
from dataclasses import dataclass

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

# A dash that marks who speaks in a dialogue: "-Look out!" — not part of the words
_DIALOGUE_DASH_RE = re.compile(r"^[-–—]+\s*")

# A line with nothing to read left, e.g. a dialogue dash whose annotation was removed
_NO_WORDS_RE = re.compile(r"^[^\w]*$")

# Credits patterns
_CREDITS_RE = re.compile(
    r"(?i)(subtitles?\s+by|opensubtitles?|sync\s+by|corrected\s+by)"
)


@dataclass(frozen=True)
class SrtCue:
    """One subtitle: its time and the lines left to read."""

    start_ms: int
    end_ms: int
    lines: tuple[str, ...]


def _srt_time_to_ms(time_str: str) -> int:
    """Convert SRT timestamp "HH:MM:SS,mmm" to milliseconds."""
    time_str = time_str.strip()
    hms, ms_part = time_str.split(",")
    h, m, s = hms.split(":")
    return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms_part)


class RegexSrtParser:
    """Reads the subtitles of an SRT file."""

    def parse_cues(self, raw_text: str) -> list[SrtCue]:
        """Subtitles with something to read, without annotations, speakers and credits."""
        cues: list[SrtCue] = []
        for block in _BLOCK_SEP_RE.split(raw_text):
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
            cues.append(SrtCue(start_ms=start_ms, end_ms=end_ms, lines=tuple(block_lines)))
        return cues

    @staticmethod
    def _strip_annotations(text_lines: list[str]) -> list[str]:
        text = _ANNOTATION_RE.sub("", "\n".join(text_lines))
        result: list[str] = []
        for line in text.splitlines():
            line = _SPEAKER_LABEL_RE.sub("", line.strip())
            line = _DIALOGUE_DASH_RE.sub("", line)
            line = _MULTI_SPACES_RE.sub(" ", line).strip()
            if not _NO_WORDS_RE.match(line):
                result.append(line)
        return result
