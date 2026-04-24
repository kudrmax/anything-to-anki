from __future__ import annotations

import gc
import logging
import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from backend.domain.ports.tts_generator import TTSGenerator

logger = logging.getLogger(__name__)

_AUDIO_BITRATE: str = "96k"
_AUDIO_CHANNELS: int = 1


class KokoroTTSGenerator(TTSGenerator):
    """Kokoro TTS adapter with lazy loading and unloading."""

    def __init__(self) -> None:
        self._pipeline: Any = None  # kokoro.KPipeline, lazy
        self._current_lang: str = ""

    def _ensure_loaded(self, lang_code: str) -> Any:  # noqa: ANN401
        """Load the Kokoro pipeline if not already loaded."""
        if self._pipeline is not None and self._current_lang == lang_code:
            return self._pipeline
        if self._pipeline is not None:
            self.unload()

        from kokoro import KPipeline

        logger.info("kokoro_tts: loading model (lang_code=%s)", lang_code)
        self._pipeline = KPipeline(lang_code=lang_code)
        self._current_lang = lang_code
        return self._pipeline

    def generate_audio(
        self, text: str, out_path: Path, voice: str, speed: float,
    ) -> None:
        """Generate TTS audio: Kokoro WAV → ffmpeg M4A."""
        import soundfile as sf

        lang_code = voice[0]  # 'a' from 'af_heart', 'b' from 'bf_emma'
        pipeline = self._ensure_loaded(lang_code)

        wav_path = out_path.with_suffix(".wav")
        m4a_path = out_path.with_suffix(".m4a")

        generator = pipeline(text, voice=voice, speed=speed)
        for _i, (_gs, _ps, audio) in enumerate(generator):
            sf.write(str(wav_path), audio, 24000)
            break  # first segment only

        self._convert_to_m4a(wav_path, m4a_path)
        wav_path.unlink(missing_ok=True)

        logger.info(
            "kokoro_tts: generated (voice=%s, speed=%.1f, out=%s)",
            voice, speed, m4a_path,
        )

    def unload(self) -> None:
        """Release model from memory."""
        if self._pipeline is None:
            return
        logger.info("kokoro_tts: unloading model")
        del self._pipeline
        self._pipeline = None
        self._current_lang = ""
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    @staticmethod
    def _convert_to_m4a(wav_path: Path, m4a_path: Path) -> None:
        """Convert WAV to M4A (AAC) using ffmpeg."""
        args = [
            "ffmpeg", "-y",
            "-i", str(wav_path),
            "-c:a", "aac",
            "-b:a", _AUDIO_BITRATE,
            "-ac", str(_AUDIO_CHANNELS),
            str(m4a_path),
        ]
        try:
            subprocess.run(args, capture_output=True, check=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            logger.exception("kokoro_tts: ffmpeg conversion failed (stderr=%s)", stderr[:500])
            raise
