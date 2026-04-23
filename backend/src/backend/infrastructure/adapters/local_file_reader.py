from __future__ import annotations

from pathlib import Path

from backend.domain.ports.file_reader import FileReader


class LocalFileReader(FileReader):
    """Reads files from local filesystem using pathlib."""

    def exists(self, path: str) -> bool:
        return Path(path).is_file()

    def read_text(self, path: str) -> str:
        p = Path(path)
        if not p.is_file():
            msg = f"File not found: {path}"
            raise FileNotFoundError(msg)
        return p.read_text(encoding="utf-8", errors="replace")
