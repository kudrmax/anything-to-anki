from __future__ import annotations

import contextlib
import logging
import os
import re
import uuid
from typing import TYPE_CHECKING

from backend.application.utils.media_names import PHRASE_FILE_PREFIX
from backend.domain.ports.media_files import MediaFiles
from backend.domain.value_objects.media_file_draft import MediaFileDraft

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

DRAFT_MARKER = ".part-"
DRAFT_ID_LENGTH = 8
# The name of a draft: nothing else in a media folder looks like it.
DRAFT_PATTERN = re.compile(
    rf"^p\d+_(screenshot|audio|tts){re.escape(DRAFT_MARKER)}[0-9a-f]{{{DRAFT_ID_LENGTH}}}\.",
)


class LocalMediaFiles(MediaFiles):
    """Media files under `{media_root}/{source_id}/p{phrase_id}_{name}`.

    The draft keeps the extension last (`p7_tts.part-1a2b.m4a`): ffmpeg and the speech
    generator pick the format by it.
    """

    def __init__(self, media_root: str) -> None:
        self._media_root = media_root

    def draft(self, source_id: int, phrase_id: int, name: str) -> MediaFileDraft:
        folder = os.path.join(self._media_root, str(source_id))
        os.makedirs(folder, exist_ok=True)
        final = f"{PHRASE_FILE_PREFIX}{phrase_id}_{name}"
        stem, extension = os.path.splitext(final)
        draft = f"{stem}{DRAFT_MARKER}{uuid.uuid4().hex[:DRAFT_ID_LENGTH]}{extension}"
        return MediaFileDraft(
            path=os.path.join(folder, draft), final_path=os.path.join(folder, final),
        )

    def keep(self, draft: MediaFileDraft) -> None:
        os.replace(draft.path, draft.final_path)

    def discard(self, draft: MediaFileDraft) -> None:
        # The app's own draft: never a file anyone else made or points at.
        with contextlib.suppress(FileNotFoundError):
            os.remove(draft.path)

    def remove(self, paths: Sequence[str]) -> None:
        root = os.path.realpath(self._media_root)
        for path in paths:
            if os.path.commonpath([root, os.path.realpath(path)]) != root:
                logger.warning("media: not removing %s, outside the media folder", path)
                continue
            with contextlib.suppress(FileNotFoundError):
                os.remove(path)
