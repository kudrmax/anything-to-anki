import os
import tempfile

import pytest
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
