import pytest
from backend.domain.value_objects.input_method import InputMethod
from backend.infrastructure.adapters.video_path_resolver import ContainerVideoPathResolver


@pytest.mark.unit
class TestContainerVideoPathResolver:
    def setup_method(self) -> None:
        self.resolver = ContainerVideoPathResolver(
            data_dir="/data",
            local_video_dir="/Users/maxos/Downloads",
            local_video_mount="/local-videos",
        )

    # --- resolve ---

    def test_resolve_youtube_relative(self) -> None:
        result = self.resolver.resolve("abc123.mp4", InputMethod.YOUTUBE_URL)
        assert result == "/data/videos/abc123.mp4"

    def test_resolve_local_relative(self) -> None:
        result = self.resolver.resolve("movie.mkv", InputMethod.VIDEO_FILE)
        assert result == "/local-videos/movie.mkv"

    def test_resolve_local_with_subdir(self) -> None:
        result = self.resolver.resolve("series/ep01.mkv", InputMethod.VIDEO_FILE)
        assert result == "/local-videos/series/ep01.mkv"

    # --- to_storage_path ---

    def test_to_storage_youtube(self) -> None:
        result = self.resolver.to_storage_path("/data/videos/abc123.mp4", InputMethod.YOUTUBE_URL)
        assert result == "abc123.mp4"

    def test_to_storage_local_host_path(self) -> None:
        result = self.resolver.to_storage_path(
            "/Users/maxos/Downloads/movie.mkv", InputMethod.VIDEO_FILE,
        )
        assert result == "movie.mkv"

    def test_to_storage_local_host_path_with_subdir(self) -> None:
        result = self.resolver.to_storage_path(
            "/Users/maxos/Downloads/series/ep01.mkv", InputMethod.VIDEO_FILE,
        )
        assert result == "series/ep01.mkv"

    def test_to_storage_local_mount_path(self) -> None:
        result = self.resolver.to_storage_path(
            "/local-videos/movie.mkv", InputMethod.VIDEO_FILE,
        )
        assert result == "movie.mkv"

    def test_to_storage_unknown_prefix_returns_as_is(self) -> None:
        resolver = ContainerVideoPathResolver(
            data_dir="/data",
            local_video_dir="",
            local_video_mount="",
        )
        result = resolver.to_storage_path("/some/random/path.mkv", InputMethod.VIDEO_FILE)
        assert result == "/some/random/path.mkv"
