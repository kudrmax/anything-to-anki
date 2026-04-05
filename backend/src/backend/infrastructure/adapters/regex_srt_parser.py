from __future__ import annotations

import re

from backend.domain.ports.source_parser import SourceParser

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

# Sound description lines: (SOUND EFFECT) or - (Sound effect)
_SOUND_DESC_RE = re.compile(r"^\s*[-–]?\s*\([A-Za-z ,']+\)\s*$")

# Speaker labels at start of line: "JOE: " or "BOY: " (2-15 chars, capitals only, no spaces)
_SPEAKER_LABEL_RE = re.compile(r"^[A-Z]{2,15}:\s*")

# Credits patterns
_CREDITS_RE = re.compile(
    r"(?i)(subtitles?\s+by|opensubtitles?|sync\s+by|corrected\s+by)"
)


class RegexSrtParser(SourceParser):
    """Parses SRT subtitle format into plain text."""

    def __init__(self) -> None:
        pass

    def parse(self, raw_text: str) -> str:
        """Convert SRT format to plain text, removing timecodes and metadata."""
        blocks = _BLOCK_SEP_RE.split(raw_text)
        collected_lines: list[str] = []

        for block in blocks:
            lines = block.splitlines()
            block_lines: list[str] = []
            skip_block = False

            for line in lines:
                # Check credits — skip entire block
                if _CREDITS_RE.search(line):
                    skip_block = True
                    break

                # Skip sequence number line
                if _SEQ_NUM_RE.match(line.strip()):
                    continue

                # Skip SRT timecode line
                if _SRT_TIMECODE_RE.match(line.strip()):
                    continue

                # Remove positional tags
                line = _POSITION_TAG_RE.sub("", line)

                # Remove HTML tags (keep content)
                line = _HTML_TAG_RE.sub("", line)

                # Skip sound description lines
                if _SOUND_DESC_RE.match(line):
                    continue

                # Remove speaker labels
                line = _SPEAKER_LABEL_RE.sub("", line)

                stripped = line.strip()
                if stripped:
                    block_lines.append(stripped)

            if not skip_block:
                collected_lines.extend(block_lines)

        return "\n".join(collected_lines)
