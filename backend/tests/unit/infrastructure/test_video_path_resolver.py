import pytest
from backend.domain.value_objects.input_method import InputMethod
from backend.infrastructure.adapters.video_path_resolver import VideoPathResolverImpl


@pytest.mark.unit
class TestVideoPathResolverImpl:
    def setup_method(self) -> None:
        self.resolver = VideoPathResolverImpl(data_dir="/data")

    # --- resolve ---

    def test_resolve_youtube_relative(self) -> None:
        result = self.resolver.resolve("abc123.mp4", InputMethod.YOUTUBE_URL)
        assert result == "/data/videos/abc123.mp4"

    def test_resolve_local_absolute(self) -> None:
        result = self.resolver.resolve("/Users/maxos/Downloads/movie.mkv", InputMethod.VIDEO_FILE)
        assert result == "/Users/maxos/Downloads/movie.mkv"

    def test_resolve_local_with_subdir(self) -> None:
        result = self.resolver.resolve("/Users/maxos/Downloads/series/ep01.mkv", InputMethod.VIDEO_FILE)
        assert result == "/Users/maxos/Downloads/series/ep01.mkv"

    # --- to_storage_path ---

    def test_to_storage_youtube(self) -> None:
        result = self.resolver.to_storage_path("/data/videos/abc123.mp4", InputMethod.YOUTUBE_URL)
        assert result == "abc123.mp4"

    def test_to_storage_local_returns_absolute(self) -> None:
        result = self.resolver.to_storage_path(
            "/Users/maxos/Downloads/movie.mkv", InputMethod.VIDEO_FILE,
        )
        assert result == "/Users/maxos/Downloads/movie.mkv"

    def test_to_storage_local_with_subdir_returns_absolute(self) -> None:
        result = self.resolver.to_storage_path(
            "/Users/maxos/Downloads/series/ep01.mkv", InputMethod.VIDEO_FILE,
        )
        assert result == "/Users/maxos/Downloads/series/ep01.mkv"
