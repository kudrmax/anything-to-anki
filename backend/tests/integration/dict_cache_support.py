"""Real dictionary cache for integration tests.

The cache is read from the same place the app reads it:
``$DICTIONARIES_DIR/.cache/dict.db``. ``make test`` exports DICTIONARIES_DIR
from ``.env`` and builds the cache beforehand. A missing cache fails the test
instead of skipping it, so the CEFR pipeline can never go silently untested.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from backend.domain.services.voting_cefr_classifier import VotingCEFRClassifier
from backend.infrastructure.adapters.cefrpy_cefr_source import CefrpyCEFRSource
from backend.infrastructure.adapters.dict_cache.cefr_source import DictCacheCEFRSource
from backend.infrastructure.adapters.dict_cache.reader import DictCacheReader

if TYPE_CHECKING:
    from backend.domain.ports.cefr_source import CEFRSource

DICTIONARIES_DIR_ENV = "DICTIONARIES_DIR"
DICT_CACHE_RELATIVE_PATH = Path(".cache") / "dict.db"
HIGH_PRIORITY = "high"


def dict_cache_path() -> Path:
    dictionaries_dir = os.environ.get(DICTIONARIES_DIR_ENV)
    if not dictionaries_dir:
        pytest.fail(f"{DICTIONARIES_DIR_ENV} is not set — run tests via `make test`")
    path = Path(dictionaries_dir) / DICT_CACHE_RELATIVE_PATH
    if not path.exists():
        pytest.fail(f"dict cache not found at {path} — run `make dict-update`")
    return path


def make_voting_classifier() -> VotingCEFRClassifier:
    reader = DictCacheReader(dict_cache_path())

    cefr_sources: list[CEFRSource] = []
    priority_sources: list[CEFRSource] = []
    for meta in reader.get_cefr_sources():
        src = DictCacheCEFRSource(reader, meta["name"])
        if meta["priority"] == HIGH_PRIORITY:
            priority_sources.append(src)
        else:
            cefr_sources.append(src)
    cefr_sources.append(CefrpyCEFRSource())

    return VotingCEFRClassifier(cefr_sources, priority_sources=priority_sources)
