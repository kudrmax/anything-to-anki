from __future__ import annotations

import json
import logging
import os
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from backend.domain.entities.candidate_tts import CandidateTTS

logger = logging.getLogger(__name__)

ALL_VOICES: list[str] = [
    "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica",
    "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck", "am_santa",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
]

_DEFAULT_SPEED: float = 1.0

if TYPE_CHECKING:
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.candidate_tts_repository import CandidateTTSRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.tts_generator import TTSGenerator


class GenerateTTSUseCase:
    """Generates TTS audio for a single candidate."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        tts_repo: CandidateTTSRepository,
        tts_generator: TTSGenerator,
        settings_repo: SettingsRepository,
        media_root: str,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._tts_repo = tts_repo
        self._tts_generator = tts_generator
        self._settings_repo = settings_repo
        self._media_root = media_root

    def execute_one(self, candidate_id: int) -> None:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            logger.warning("generate_tts: candidate %d not found", candidate_id)
            return

        text = candidate.context_fragment
        if not text:
            logger.warning("generate_tts: candidate %d has no context_fragment", candidate_id)
            return

        voice = self._pick_voice()
        speed = self._get_speed()

        out_dir = os.path.join(self._media_root, str(candidate.source_id))
        os.makedirs(out_dir, exist_ok=True)
        out_path = Path(out_dir) / f"{candidate_id}_tts.m4a"

        self._tts_generator.generate_audio(text, out_path, voice, speed)

        self._tts_repo.upsert(CandidateTTS(
            candidate_id=candidate_id,
            audio_path=str(out_path),
            generated_at=datetime.now(tz=UTC),
        ))

        logger.info(
            "generate_tts: done (candidate=%d, voice=%s, speed=%.1f)",
            candidate_id, voice, speed,
        )

    def _pick_voice(self) -> str:
        raw = self._settings_repo.get("tts_enabled_voices")
        if raw:
            enabled: list[str] = json.loads(raw)
            if enabled:
                return random.choice(enabled)  # noqa: S311
        return random.choice(ALL_VOICES)  # noqa: S311

    def _get_speed(self) -> float:
        raw = self._settings_repo.get("tts_speed")
        if raw:
            try:
                return float(raw)
            except ValueError:
                pass
        return _DEFAULT_SPEED
