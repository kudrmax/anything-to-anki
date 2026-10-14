from __future__ import annotations

import json
import logging
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from backend.application.utils.media_names import TTS_FILE
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
    from backend.application.utils.job_phrases import JobPhrases
    from backend.domain.ports.candidate_tts_repository import CandidateTTSRepository
    from backend.domain.ports.media_files import MediaFiles
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.tts_generator import TTSGenerator
    from backend.domain.value_objects.phrase_ref import PhraseRef


class GenerateTTSUseCase:
    """Generates TTS audio for one phrase; a phrase a Rebuild changed meanwhile gets none."""

    def __init__(
        self,
        job_phrases: JobPhrases,
        tts_repo: CandidateTTSRepository,
        tts_generator: TTSGenerator,
        settings_repo: SettingsRepository,
        media_files: MediaFiles,
    ) -> None:
        self._job_phrases = job_phrases
        self._tts_repo = tts_repo
        self._tts_generator = tts_generator
        self._settings_repo = settings_repo
        self._media_files = media_files

    def execute_one(self, phrase: PhraseRef) -> None:
        card = self._job_phrases.card(phrase)
        if card is None:
            return

        text = " ".join(card.phrase.phrase.text.split())
        if not text:
            logger.warning("generate_tts: phrase %d has no text", card.phrase_id)
            return

        voice = self._pick_voice()
        speed = self._get_speed()
        speech = self._media_files.draft(card.word.source_id, card.phrase_id, TTS_FILE)
        try:
            self._tts_generator.generate_audio(text, Path(speech.path), voice, speed)
            if not self._job_phrases.holds(card):
                return
            self._media_files.keep(speech)
        finally:
            self._media_files.discard(speech)
        self._tts_repo.upsert_for_phrase(card.phrase_id, CandidateTTS(
            candidate_id=card.word_id,
            audio_path=speech.final_path,
            generated_at=datetime.now(tz=UTC),
        ))

        logger.info(
            "generate_tts: done (phrase=%d, voice=%s, speed=%.1f)",
            card.phrase_id, voice, speed,
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
