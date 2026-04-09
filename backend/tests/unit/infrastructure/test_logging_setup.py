"""Smoke-тесты для configure_logging — формат и наличие layer."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.infrastructure.logging_setup import configure_logging

if TYPE_CHECKING:
    import pytest


def test_configure_logging_emits_layer_and_message(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("test_layer")
    logging.getLogger("backend.sample").info("hello world")

    out = capsys.readouterr().out
    assert "hello world" in out
    assert "test_layer" in out
    assert "backend.sample" in out
    assert "info" in out.lower()


def test_configure_logging_respects_log_level_env(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    configure_logging("test_layer")
    log = logging.getLogger("backend.sample.warning_test")
    log.info("should be hidden")
    log.warning("should be visible")

    out = capsys.readouterr().out
    assert "should be hidden" not in out
    assert "should be visible" in out
