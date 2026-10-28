from __future__ import annotations

from pydantic import BaseModel

from backend.domain.value_objects.generation_blocker import (
    GenerationBlocker,  # noqa: TC001 — pydantic field type
)
from backend.domain.value_objects.generation_kind import (
    GenerationKind,  # noqa: TC001 — pydantic field type
)


class GenerationKindStatusDTO(BaseModel):
    """How far one kind of generation got over the source's cards.

    `done + running + failed + missing == total`;
    `next`, `missing`, `ready_next`, `ready_missing`, `ready_all`, `all` count the cards
    each scope would take;
    `failed` counts the cards of the failed scope.
    """

    kind: GenerationKind
    total: int
    done: int
    running: int
    failed: int
    next: int
    missing: int
    ready_next: int
    ready_missing: int
    ready_all: int
    all: int
    blocked_by: GenerationBlocker | None = None
    # Sources whose video this kind needs and nobody downloads yet: neither here nor on its way.
    videos_to_download: int = 0


class GenerationStatusDTO(BaseModel):
    kinds: list[GenerationKindStatusDTO]
    in_progress: bool
    # How many cards the scopes that take a batch take at most.
    batch_size: int
