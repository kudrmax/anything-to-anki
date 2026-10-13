from __future__ import annotations

from pathlib import Path

from backend.domain.exceptions import NotATextFileError
from backend.domain.ports.file_reader import FileReader

_UTF16_BOMS: tuple[bytes, ...] = (b"\xff\xfe", b"\xfe\xff")
# A NUL byte never occurs in text, while every binary format has plenty early on.
_BINARY_PROBE_BYTES = 8192
_NUL = b"\x00"
# Old text files that aren't UTF-8 are usually Windows-1252: curly quotes and dashes survive.
_LEGACY_ENCODING = "cp1252"


class LocalFileReader(FileReader):
    """Reads files from local filesystem using pathlib."""

    def exists(self, path: str) -> bool:
        return Path(path).is_file()

    def read_text(self, path: str) -> str:
        p = Path(path)
        if not p.is_file():
            msg = f"File not found: {path}"
            raise FileNotFoundError(msg)
        raw = p.read_bytes()
        if raw.startswith(_UTF16_BOMS):
            return raw.decode("utf-16", errors="replace")
        if _NUL in raw[:_BINARY_PROBE_BYTES]:
            raise NotATextFileError(path)
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw.decode(_LEGACY_ENCODING, errors="replace")
