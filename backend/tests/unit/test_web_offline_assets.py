"""Инвариант: первый экран веб-фронтенда не зависит от сети.

Приложение локальное и часто запускается без доступа в интернет (или с
корпоративным VPN, режущим внешние хосты). Любой внешний ресурс, подключённый
в `index.html` до бандла, — это render-blocking запрос: пока браузер его не
разрешит, JS не выполняется и пользователь смотрит на белую страницу.

Регрессия, ради которой написан тест: `<link rel="stylesheet">` на
fonts.googleapis.com держал первый рендер до таймаута. Шрифты должны
приезжать из собственного бандла (@fontsource), а не из интернета.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = REPO_ROOT / "frontends" / "web"
INDEX_HTML = WEB_ROOT / "index.html"
SRC_DIR = WEB_ROOT / "src"

# Ссылки на внешние хосты в разметке: href="https://…" / src="http://…"
EXTERNAL_MARKUP_REF = re.compile(r"""(?:href|src)\s*=\s*["']https?://""", re.IGNORECASE)

# Внешние ресурсы в CSS: @import "https://…" / url(https://…)
EXTERNAL_CSS_REF = re.compile(r"""(?:@import\s+|url\(\s*)["']?https?://""", re.IGNORECASE)


@pytest.mark.unit
def test_index_html_has_no_external_resources() -> None:
    """index.html не подключает ничего из интернета — иначе рендер блокируется."""
    offending = [
        line.strip()
        for line in INDEX_HTML.read_text(encoding="utf-8").splitlines()
        if EXTERNAL_MARKUP_REF.search(line)
    ]

    assert not offending, (
        "index.html подключает внешние ресурсы — они блокируют первый рендер "
        f"при недоступной сети: {offending}"
    )


@pytest.mark.unit
def test_frontend_css_has_no_external_resources() -> None:
    """CSS фронтенда не тянет шрифты и стили с внешних хостов."""
    offending: list[str] = []
    for css_file in sorted(SRC_DIR.rglob("*.css")):
        for line in css_file.read_text(encoding="utf-8").splitlines():
            if EXTERNAL_CSS_REF.search(line):
                offending.append(f"{css_file.relative_to(REPO_ROOT)}: {line.strip()}")

    assert not offending, (
        f"CSS фронтенда обращается к внешним хостам: {offending}"
    )
