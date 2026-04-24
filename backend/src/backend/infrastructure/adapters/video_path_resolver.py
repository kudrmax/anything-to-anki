from __future__ import annotations

import os

from backend.domain.ports.video_path_resolver import VideoPathResolver
from backend.domain.value_objects.input_method import InputMethod


class VideoPathResolverImpl(VideoPathResolver):
    """Resolves video paths.

    YouTube videos: stored as relative filename, resolved to {data_dir}/videos/{filename}.
    Local videos: stored as absolute path, returned as-is.
    """

    def __init__(self, data_dir: str) -> None:
        self._youtube_base = os.path.join(data_dir, "videos")

    def resolve(self, stored_path: str, input_method: InputMethod) -> str:
        if input_method == InputMethod.YOUTUBE_URL:
            return os.path.join(self._youtube_base, stored_path)
        # Local video: absolute path stored directly
        return stored_path

    def to_storage_path(self, absolute_path: str, input_method: InputMethod) -> str:
        if input_method == InputMethod.YOUTUBE_URL:
            prefix = self._youtube_base + "/"
            if absolute_path.startswith(prefix):
                return absolute_path[len(prefix):]
            return os.path.basename(absolute_path)
        # Local video: store absolute path as-is
        return absolute_path
