"""What a rebuild may do to a phrase: the user's work on it is never lost."""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from backend.domain.value_objects.occurrence_row import OccurrenceRow


def is_untouchable(o: OccurrenceRow) -> bool:
    """A rebuild never changes the text or results of the phrase, nor deletes it."""
    return (
        o.is_decision
        or o.exported
        or o.edited_by_user
        or o.shown_by is ShownBy.USER
        or o.origin is not OccurrenceOrigin.AUTO
    )


def is_touched(o: OccurrenceRow, word_decided: bool) -> bool:
    """Something of the user's is on the phrase: no rebuild deletes it for being gone from
    the analysis, unless asked to rebuild open cards too and it is not untouchable."""
    return (
        has_user_work(o, word_decided)
        or o.shown_by is ShownBy.USER
        or o.origin is not OccurrenceOrigin.AUTO
    )


def has_user_work(o: OccurrenceRow, word_decided: bool) -> bool:
    """The user did something with the phrase, whatever its origin: decided on it,
    exported it, edited, generated for it, queued work on it or skipped it."""
    return (
        o.is_decision
        or o.exported
        or o.edited_by_user
        or o.has_results
        or o.has_active_job
        or o.skipped
        or (o.is_shown and word_decided)
    )
