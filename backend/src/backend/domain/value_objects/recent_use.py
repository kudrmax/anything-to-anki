from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.value_objects.source_scope import ScopeKind

if TYPE_CHECKING:
    from datetime import datetime

    from backend.domain.value_objects.source_scope import SourceScope

USED_KINDS = frozenset({ScopeKind.SOURCE, ScopeKind.COLLECTION})


@dataclass(frozen=True)
class RecentUse:
    """The last moment the user worked with a source or a collection: added it or opened
    its review."""

    scope: SourceScope
    used_at: datetime

    def __post_init__(self) -> None:
        if self.scope.kind not in USED_KINDS:
            msg = f"Only a source or a collection is used, not {self.scope.kind}"
            raise ValueError(msg)
