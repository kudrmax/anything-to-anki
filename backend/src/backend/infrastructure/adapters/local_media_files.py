from __future__ import annotations

import contextlib
import os
import uuid

from backend.application.utils.media_names import PHRASE_FILE_PREFIX
from backend.domain.ports.media_files import MediaFiles
from backend.domain.value_objects.media_file_draft import MediaFileDraft

DRAFT_MARKER = ".part-"


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
        draft = f"{stem}{DRAFT_MARKER}{uuid.uuid4().hex[:8]}{extension}"
        return MediaFileDraft(
            path=os.path.join(folder, draft), final_path=os.path.join(folder, final),
        )

    def keep(self, draft: MediaFileDraft) -> None:
        os.replace(draft.path, draft.final_path)

    def discard(self, draft: MediaFileDraft) -> None:
        # The app's own draft: never a file anyone else made or points at.
        with contextlib.suppress(FileNotFoundError):
            os.remove(draft.path)
