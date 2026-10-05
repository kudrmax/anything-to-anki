"""Извлечение скриншота должно работать на любой сборке ffmpeg.

Юнит-тесты адаптера мокают ``subprocess.run`` и потому слепы к тому, какие
кодеки реально собраны в системном ffmpeg. Именно поэтому незамеченным прошёл
переход homebrew/core на «худую» сборку без libwebp: команда ffmpeg осталась
прежней, а кодера не стало — скриншоты перестали генерироваться молча.

Здесь ffmpeg запускается по-настоящему. Фикстурное видео кодируется ``mpeg4``:
это встроенный кодер, который есть в любой сборке. Брать ``libx264`` нельзя —
он такой же опциональный, как libwebp, и тест наступил бы на те же грабли,
которые проверяет.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest
from backend.infrastructure.adapters.ffmpeg_media_extractor import FfmpegMediaExtractor
from backend.infrastructure.adapters.pillow_card_picture_encoder import PillowCardPictureEncoder

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed"),
]

_WEBP_RIFF_HEADER = b"RIFF"
_WEBP_FORMAT_MARKER = b"WEBP"
_WEBP_FORMAT_OFFSET = 8
_FIXTURE_DURATION_S = 2
_FIXTURE_SIZE = "320x240"


@pytest.fixture
def video_file(tmp_path: Path) -> Path:
    """Синтетическое видео, не требующее внешних файлов и опциональных кодеков."""
    path = tmp_path / "fixture.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"testsrc=size={_FIXTURE_SIZE}:duration={_FIXTURE_DURATION_S}:rate=10",
            "-c:v", "mpeg4",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return path


def _extractor() -> FfmpegMediaExtractor:
    return FfmpegMediaExtractor(PillowCardPictureEncoder())


def test_extract_screenshot_writes_real_webp(video_file: Path, tmp_path: Path) -> None:
    """На выходе — валидный WebP, а не пустой файл и не молчаливый пропуск."""
    out_path = tmp_path / "1_screenshot.webp"

    _extractor().extract_screenshot(str(video_file), 1000, str(out_path))

    assert out_path.exists()
    data = out_path.read_bytes()
    assert data, "скриншот пустой"
    assert data[:4] == _WEBP_RIFF_HEADER
    assert data[_WEBP_FORMAT_OFFSET:_WEBP_FORMAT_OFFSET + 4] == _WEBP_FORMAT_MARKER


def test_extract_screenshot_fails_loudly_past_end_of_video(
    video_file: Path, tmp_path: Path,
) -> None:
    """Кадра за пределами длительности нет — это ошибка, а не пустой файл.

    ffmpeg в такой ситуации завершается с кодом 0 и ничего не выводит, поэтому
    без явной проверки поломка выглядела бы как успешно созданный скриншот.
    """
    out_path = tmp_path / "2_screenshot.webp"
    past_end_ms = (_FIXTURE_DURATION_S + 60) * 1000

    with pytest.raises(RuntimeError):
        _extractor().extract_screenshot(str(video_file), past_end_ms, str(out_path))

    assert not out_path.exists(), "недоделанный скриншот не должен оставаться на диске"
