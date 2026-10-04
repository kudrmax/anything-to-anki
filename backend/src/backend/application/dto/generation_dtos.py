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

    `done + running + failed + missing == total`.
    """

    kind: GenerationKind
    total: int
    done: int
    running: int
    failed: int
    missing: int
    blocked_by: GenerationBlocker | None = None


class GenerationStatusDTO(BaseModel):
    kinds: list[GenerationKindStatusDTO]
    in_progress: bool
