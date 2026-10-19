"""What a rebuild may do to a phrase: the user's work on it is never lost."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.services.card_view import is_protected

if TYPE_CHECKING:
    from backend.domain.value_objects.occurrence_row import OccurrenceRow


def is_untouchable(o: OccurrenceRow) -> bool:
    """The card is protected (`card_view.is_protected`): a rebuild never changes its text or
    results, nor deletes it."""
    return is_protected(o.card_state, o.user_work)


def is_touched(o: OccurrenceRow, word_decided: bool) -> bool:
    """Something of the user's is on the phrase: no rebuild deletes it for being gone from
    the analysis, unless asked to rebuild open cards too and it is not untouchable. Besides
    protection: results, a queued job, or shown at a decided word."""
    return (
        is_untouchable(o)
        or o.has_results
        or o.has_active_job
        or (o.is_shown and word_decided)
    )
