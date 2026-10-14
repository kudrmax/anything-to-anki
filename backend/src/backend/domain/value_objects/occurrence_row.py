from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy


@dataclass(frozen=True)
class OccurrenceRow:
    """A light view of a phrase: what deciding about it needs, without its texts and results.

    `text_hash` identifies the source text of the phrase (see `hash_text`).
    """

    id: int
    candidate_id: int
    key: OccurrenceKey | None
    origin: OccurrenceOrigin
    shown_by: ShownBy | None
    skipped: bool
    is_decision: bool
    revision: int
    edited_by_user: bool
    has_results: bool
    exported: bool
    has_active_job: bool
    text_hash: str

    @staticmethod
    def hash_text(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()
