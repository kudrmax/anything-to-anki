"""Единая настройка логирования для всех entrypoint'ов проекта.

Используется как:

    from backend.infrastructure.logging_setup import configure_logging
    configure_logging("app")  # или "worker", "ai_proxy"

После вызова все стандартные `logging.getLogger(__name__).info(...)` будут
проходить через structlog ConsoleRenderer и иметь единый формат:

    2026-04-10T14:23:45 [info     ] message_text  layer=app logger=backend.x key=value

Поведение для всех слоёв одинаковое: pretty-rendered, человекочитаемый формат.
JSON-режим намеренно не реализован — это локальное приложение, JSON не нужен.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Final

import structlog

DEFAULT_LEVEL: Final[str] = "INFO"
LEVEL_ENV_VAR: Final[str] = "LOG_LEVEL"
NOISY_LOGGERS: Final[tuple[str, ...]] = ("httpx", "httpcore", "urllib3", "asyncio")


def configure_logging(layer: str) -> None:
    """Настроить structlog + stdlib logging для текущего процесса.

    `layer` — короткий ярлык слоя, который будет в каждой строке логов:
    'app', 'worker', 'ai_proxy'. Это позволяет в общем потоке `make logs`
    мгновенно понимать, откуда строка.
    """
    level_name = os.getenv(LEVEL_ENV_VAR, DEFAULT_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)

    timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%dT%H:%M:%S", utc=False)

    # NB: format_exc_info намеренно ОТСУТСТВУЕТ — ConsoleRenderer сам красиво
    # форматирует исключения, а format_exc_info с ним конфликтует.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_layer(layer),
        timestamper,
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Удаляем хендлеры, которые мог поставить uvicorn/arq/basicConfig до нас.
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # Снижаем шум от чрезмерно болтливых сторонних логгеров,
    # но не глушим их полностью.
    for noisy in NOISY_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _add_layer(layer: str) -> structlog.types.Processor:
    def processor(
        _logger: logging.Logger,
        _method: str,
        event_dict: structlog.types.EventDict,
    ) -> structlog.types.EventDict:
        event_dict.setdefault("layer", layer)
        return event_dict

    return processor
