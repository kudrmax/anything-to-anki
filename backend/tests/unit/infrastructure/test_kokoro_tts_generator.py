from __future__ import annotations

import gc
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from backend.infrastructure.adapters.kokoro_tts_generator import (
    KokoroTTSGenerator,
    _AUDIO_BITRATE,
    _AUDIO_CHANNELS,
)


@pytest.mark.unit
class TestConvertToM4a:
    def test_calls_ffmpeg_with_correct_args(self, tmp_path: Path) -> None:
        wav = tmp_path / "test.wav"
        m4a = tmp_path / "test.m4a"

        with patch("subprocess.run") as mock_run:
            KokoroTTSGenerator._convert_to_m4a(wav, m4a)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "ffmpeg"
            assert "-y" in args
            assert str(wav) in args
            assert str(m4a) in args
            assert "-c:a" in args
            assert "aac" in args
            assert "-b:a" in args
            assert _AUDIO_BITRATE in args
            assert "-ac" in args
            assert str(_AUDIO_CHANNELS) in args
            assert mock_run.call_args[1]["capture_output"] is True
            assert mock_run.call_args[1]["check"] is True

    def test_raises_on_ffmpeg_failure(self, tmp_path: Path) -> None:
        wav = tmp_path / "test.wav"
        m4a = tmp_path / "test.m4a"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "ffmpeg", stderr=b"error details",
            )
            with pytest.raises(subprocess.CalledProcessError):
                KokoroTTSGenerator._convert_to_m4a(wav, m4a)


@pytest.mark.unit
class TestUnload:
    def test_unload_when_pipeline_is_none_is_noop(self) -> None:
        gen = KokoroTTSGenerator()
        assert gen._pipeline is None
        # Should not raise
        gen.unload()
        assert gen._pipeline is None

    def test_unload_when_pipeline_loaded_deletes_and_collects(self) -> None:
        gen = KokoroTTSGenerator()
        gen._pipeline = MagicMock()
        gen._current_lang = "a"

        with patch("gc.collect") as mock_gc:
            gen.unload()

            assert gen._pipeline is None
            assert gen._current_lang == ""
            mock_gc.assert_called_once()


@pytest.mark.unit
class TestGenerateAudio:
    def test_calls_pipeline_with_correct_voice_and_speed(self, tmp_path: Path) -> None:
        import sys

        mock_sf = MagicMock()
        sys.modules["soundfile"] = mock_sf

        try:
            gen = KokoroTTSGenerator()

            mock_pipeline = MagicMock()
            mock_audio = MagicMock()
            mock_pipeline.return_value = iter([(None, None, mock_audio)])

            out_path = tmp_path / "out.m4a"

            with (
                patch.object(gen, "_ensure_loaded", return_value=mock_pipeline),
                patch.object(gen, "_convert_to_m4a") as mock_convert,
            ):
                wav_path = tmp_path / "out.wav"
                wav_path.touch()

                gen.generate_audio("Hello world", out_path, "af_heart", 0.9)

                mock_pipeline.assert_called_once_with(
                    "Hello world", voice="af_heart", speed=0.9,
                )
                mock_sf.write.assert_called_once()
                mock_convert.assert_called_once()
        finally:
            del sys.modules["soundfile"]

    def test_ensure_loaded_uses_first_char_as_lang_code(self, tmp_path: Path) -> None:
        import sys

        mock_sf = MagicMock()
        sys.modules["soundfile"] = mock_sf

        try:
            gen = KokoroTTSGenerator()

            mock_pipeline = MagicMock()
            mock_pipeline.return_value = iter([(None, None, MagicMock())])

            out_path = tmp_path / "out.m4a"

            with (
                patch.object(gen, "_ensure_loaded", return_value=mock_pipeline) as mock_ensure,
                patch.object(gen, "_convert_to_m4a"),
            ):
                wav_path = tmp_path / "out.wav"
                wav_path.touch()
                gen.generate_audio("text", out_path, "bf_emma", 1.0)
                mock_ensure.assert_called_once_with("b")
        finally:
            del sys.modules["soundfile"]


@pytest.mark.unit
class TestEnsureLoaded:
    def test_reloads_when_lang_changes(self) -> None:
        gen = KokoroTTSGenerator()
        gen._pipeline = MagicMock()
        gen._current_lang = "a"

        with (
            patch.object(gen, "unload") as mock_unload,
            patch("backend.infrastructure.adapters.kokoro_tts_generator.KPipeline", create=True) as mock_kpipeline_cls,
        ):
            # Patch the import inside _ensure_loaded
            mock_new_pipeline = MagicMock()

            import sys
            mock_kokoro = MagicMock()
            mock_kokoro.KPipeline.return_value = mock_new_pipeline
            sys.modules["kokoro"] = mock_kokoro

            try:
                result = gen._ensure_loaded("b")
                mock_unload.assert_called_once()
                assert gen._current_lang == "b"
                assert result == mock_new_pipeline
            finally:
                del sys.modules["kokoro"]

    def test_reuses_pipeline_for_same_lang(self) -> None:
        gen = KokoroTTSGenerator()
        existing = MagicMock()
        gen._pipeline = existing
        gen._current_lang = "a"

        result = gen._ensure_loaded("a")
        assert result is existing
