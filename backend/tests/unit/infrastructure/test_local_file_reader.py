import os
import tempfile
from pathlib import Path

import pytest
from backend.domain.exceptions import NotATextFileError
from backend.infrastructure.adapters.local_file_reader import LocalFileReader


@pytest.mark.unit
class TestLocalFileReader:
    def test_exists_returns_true_for_existing_file(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello")
            path = f.name
        try:
            reader = LocalFileReader()
            assert reader.exists(path) is True
        finally:
            os.unlink(path)

    def test_exists_returns_false_for_missing_file(self) -> None:
        reader = LocalFileReader()
        assert reader.exists("/nonexistent/path/file.txt") is False

    def test_read_text_returns_file_content(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            path = f.name
        try:
            reader = LocalFileReader()
            assert reader.read_text(path) == "hello world"
        finally:
            os.unlink(path)

    def test_read_text_raises_for_missing_file(self) -> None:
        reader = LocalFileReader()
        with pytest.raises(FileNotFoundError):
            reader.read_text("/nonexistent/path/file.txt")

    def test_read_text_handles_utf8_bom_and_utf16(self, tmp_path: Path) -> None:
        utf8 = tmp_path / "a.txt"
        utf8.write_bytes("\ufeffcafé".encode())
        utf16 = tmp_path / "b.txt"
        utf16.write_text("café", encoding="utf-16")
        reader = LocalFileReader()
        assert reader.read_text(str(utf8)) == "café"
        assert reader.read_text(str(utf16)) == "café"

    def test_read_text_falls_back_to_windows_encoding(self, tmp_path: Path) -> None:
        path = tmp_path / "old.txt"
        path.write_bytes("“Quoted” — dash".encode("cp1252"))
        assert LocalFileReader().read_text(str(path)) == "“Quoted” — dash"

    def test_read_text_rejects_binary_file(self, tmp_path: Path) -> None:
        path = tmp_path / "book.pdf"
        path.write_bytes(b"%PDF-1.7\n\x00\x01\x02 binary")
        with pytest.raises(NotATextFileError):
            LocalFileReader().read_text(str(path))
