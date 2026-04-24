"""TTS provider comparison script.

Generates audio for a test sentence using multiple TTS providers.
Results are saved to data/tts_test/ for manual listening.

Usage:
    source scripts/tts_test_venv/bin/activate
    python scripts/test_tts_providers.py
    python scripts/test_tts_providers.py "Custom sentence to test"
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "tts_test"
DEFAULT_TEXT = (
    "She couldn't help but procrastinate, "
    "even though the deadline was looming."
)


def _print_result(name: str, path: Path | None, elapsed: float, error: str | None) -> None:
    if error:
        print(f"  SKIP  {name}: {error}")
    else:
        assert path is not None
        size_kb = path.stat().st_size / 1024
        print(f"  OK    {name}: {path.name} ({size_kb:.0f} KB, {elapsed:.1f}s)")


def test_edge_tts(text: str, out_path: Path) -> None:
    """edge-tts: Microsoft Edge neural voices (Azure)."""
    try:
        import edge_tts
    except ImportError:
        raise ImportError("pip install edge-tts")

    async def _generate() -> None:
        communicate = edge_tts.Communicate(text, voice="en-US-AriaNeural")
        await communicate.save(str(out_path))

    asyncio.run(_generate())


def test_kokoro(text: str, out_path: Path) -> None:
    """Kokoro 82M: lightweight neural TTS."""
    try:
        import kokoro
    except ImportError:
        raise ImportError("pip install kokoro soundfile (requires Python <3.13)")

    pipeline = kokoro.KPipeline(lang_code="a")
    generator = pipeline(text, voice="af_heart")
    for i, (gs, ps, audio) in enumerate(generator):
        if i == 0:
            import soundfile as sf

            sf.write(str(out_path), audio, 24000)
            break


def test_coqui(text: str, out_path: Path) -> None:
    """Coqui XTTS v2: deep learning TTS toolkit."""
    try:
        from TTS.api import TTS as CoquiTTS
    except ImportError:
        raise ImportError("pip install coqui-tts")

    tts = CoquiTTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
    tts.tts_to_file(text=text, file_path=str(out_path))


def test_piper(text: str, out_path: Path) -> None:
    """Piper: fast local neural TTS (VITS + ONNX)."""
    try:
        from piper import PiperVoice  # noqa: F401 — import check only
    except ImportError:
        raise ImportError("pip install piper-tts")

    model_dir = Path.home() / ".local" / "share" / "piper-tts"
    model_path = model_dir / "en_US-lessac-medium.onnx"
    if not model_path.exists():
        raise RuntimeError(
            f"Piper model not found at {model_path}. "
            "Download from huggingface.co/rhasspy/piper-voices"
        )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "piper",
            "--model",
            str(model_path),
            "--output_file",
            str(out_path),
        ],
        input=text.encode(),
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"piper failed: {result.stderr.decode()}")


def test_gtts(text: str, out_path: Path) -> None:
    """gTTS: Google Translate text-to-speech."""
    try:
        from gtts import gTTS
    except ImportError:
        raise ImportError("pip install gTTS")

    tts = gTTS(text=text, lang="en", tld="com")
    tts.save(str(out_path))


PROVIDERS = [
    ("01_edge_tts", "edge-tts", test_edge_tts, ".mp3"),
    ("02_kokoro", "Kokoro 82M", test_kokoro, ".wav"),
    ("03_coqui", "Coqui TTS", test_coqui, ".wav"),
    ("04_piper", "Piper", test_piper, ".wav"),
    ("05_gtts", "gTTS", test_gtts, ".mp3"),
]


def main() -> None:
    text = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TEXT

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Text: {text!r}\n")
    print(f"Output: {OUTPUT_DIR}\n")
    print("Results:")

    for key, name, func, ext in PROVIDERS:
        out_path = OUTPUT_DIR / f"{key}{ext}"

        start = time.monotonic()
        try:
            func(text, out_path)
            elapsed = time.monotonic() - start
            _print_result(name, out_path, elapsed, None)
        except ImportError as e:
            _print_result(name, None, 0, str(e))
        except Exception as e:
            _print_result(name, None, 0, f"ERROR: {e}")

    print(f"\nDone. Listen to files in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
