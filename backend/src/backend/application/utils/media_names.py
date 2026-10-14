"""Names of the media files made for a phrase, in the folder of its source."""
from __future__ import annotations

import os

PHRASE_FILE_PREFIX = "p"
SCREENSHOT_FILE = "screenshot.webp"
AUDIO_FILE = "audio.m4a"
TTS_FILE = "tts.m4a"


def phrase_file(media_root: str, source_id: int, phrase_id: int, name: str) -> str:
    """`{media_root}/{source_id}/p{phrase_id}_{name}`; the folder is made if missing."""
    folder = os.path.join(media_root, str(source_id))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{PHRASE_FILE_PREFIX}{phrase_id}_{name}")
