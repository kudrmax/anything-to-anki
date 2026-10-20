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

