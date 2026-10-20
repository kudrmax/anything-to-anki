from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.generation_blocker import GenerationBlocker

if TYPE_CHECKING:
    from collections.abc import Sequence


def set_blocker(blockers: Sequence[GenerationBlocker | None]) -> GenerationBlocker | None:
    """What holds a kind of generation back on a set of sources: nothing while some source
    can run it; otherwise a download under way, as it frees the kind by itself, before a
    video nobody downloads."""
    if not blockers or None in blockers:
        return None
    if GenerationBlocker.VIDEO_DOWNLOADING in blockers:
        return GenerationBlocker.VIDEO_DOWNLOADING
    return GenerationBlocker.VIDEO_NOT_DOWNLOADED
