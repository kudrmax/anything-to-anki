from __future__ import annotations

import os

from backend.domain.ports.video_path_resolver import VideoPathResolver
from backend.domain.value_objects.input_method import InputMethod


class ContainerVideoPathResolver(VideoPathResolver):
    """Resolves video paths for a Docker container environment.

    YouTube videos live in {data_dir}/videos/.
    Local videos are mounted from host LOCAL_VIDEO_DIR at LOCAL_VIDEO_MOUNT.
    """

    def __init__(
        self,
        data_dir: str,
        local_video_dir: str,
        local_video_mount: str,
    ) -> None:
        self._youtube_base = os.path.join(data_dir, "videos")
        self._local_video_dir = local_video_dir
        self._local_video_mount = local_video_mount

    def resolve(self, stored_path: str, input_method: InputMethod) -> str:
        # Backward compat: absolute paths from old DB entries — return as-is
        if os.path.isabs(stored_path):
            return stored_path
        if input_method == InputMethod.YOUTUBE_URL:
            return os.path.join(self._youtube_base, stored_path)
        return os.path.join(self._local_video_mount, stored_path)

    def to_storage_path(self, absolute_path: str, input_method: InputMethod) -> str:
        if input_method == InputMethod.YOUTUBE_URL:
            # Strip youtube base prefix
            prefix = self._youtube_base + "/"
            if absolute_path.startswith(prefix):
                return absolute_path[len(prefix):]
            return os.path.basename(absolute_path)
        # Local: strip host LOCAL_VIDEO_DIR prefix
        if self._local_video_dir:
            prefix = self._local_video_dir.rstrip("/") + "/"
            if absolute_path.startswith(prefix):
                return absolute_path[len(prefix):]
        # Fallback: strip mount prefix
        if self._local_video_mount:
            prefix = self._local_video_mount.rstrip("/") + "/"
            if absolute_path.startswith(prefix):
                return absolute_path[len(prefix):]
        return absolute_path
