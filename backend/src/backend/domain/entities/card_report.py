from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class CardReport:
    """The user's complaint about a card, with a snapshot of the card.

    The snapshot keeps the report meaningful after the candidate is
    reprocessed or its source deleted — it is what gets analysed later.
    """

    source_id: int
    source_title: str
    candidate_id: int
    lemma: str
    surface_form: str | None
    context_fragment: str
    zipf_frequency: float
    cefr_level: str | None
    fragment_unknown_count: int
    is_phrasal_verb: bool
    comment: str
    # Source text around the phrase; None when the phrase is not in the source.
    text_before: str | None = None
    text_after: str | None = None
    id: int | None = None
    created_at: datetime | None = None
