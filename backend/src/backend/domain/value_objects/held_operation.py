from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.source_operation_kind import SourceOperationKind


@dataclass(frozen=True)
class HeldOperation:
    """The operation a source is busy with."""

    kind: SourceOperationKind
