from __future__ import annotations

import gc
from functools import cache


@cache
def freeze_startup_heap() -> None:
    """What start-up made lives as long as the process, so the collector stops walking it:
    a full collection over it took ~70 ms of a frequent lemma's projection. Once per
    process: what is frozen is never collected."""
    gc.freeze()
