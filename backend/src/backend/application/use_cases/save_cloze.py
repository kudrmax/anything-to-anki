from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.utils.source_free import ensure_source_free
from backend.domain.entities.candidate_cloze import CandidateCloze
from backend.domain.exceptions import (
    ClozeNotAllowedError,
    ClozePhraseChangedError,
    InvalidClozeError,
    PhraseNotFoundError,
)
from backend.domain.value_objects.card_choice import NoteKind, Press, export_kind
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

if TYPE_CHECKING:
    from backend.application.dto.source_dtos import CardDTO
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.application.utils.card_views import CardViews
    from backend.domain.ports.candidate_cloze_repository import CandidateClozeRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.source_operation_lock import SourceOperationLock
    from backend.domain.services.cloze_builder import ClozeBuilder


class SaveClozeUseCase:
    """Saves which words of the phrase the cloze card hides: Cloze pressed on the phrase.

    The editor's Save is the press: a card not a cloze yet becomes one by the press table
    (a card in Anki of the other kind too: its next export makes a cloze note). A cloze
    already in Anki keeps its markup, as Anki holds it."""

    def __init__(
        self,
        occurrence_repo: OccurrenceRepository,
        candidate_repo: CandidateRepository,
        cloze_repo: CandidateClozeRepository,
        card_views: CardViews,
        decide_phrase: DecidePhraseUseCase,
        builder: ClozeBuilder,
        lock: SourceOperationLock,
    ) -> None:
        self._lock = lock
        self._occurrences = occurrence_repo
        self._candidate_repo = candidate_repo
        self._cloze_repo = cloze_repo
        self._card_views = card_views
        self._decide_phrase = decide_phrase
        self._builder = builder

    def execute(
        self,
        occurrence_id: int,
        phrase: str,
        hidden_word_indices: list[int],
        hint_kind: ClozeHintKind,
        custom_hint: str | None,
    ) -> CardDTO:
        """Returns the card as it is after saving.

        `phrase` is the card phrase the user picked the words in: if the card shows another
        one by now (polish landed or was reverted), the indices point at other words."""
        occ = self._occurrences.get(occurrence_id)
        word = self._candidate_repo.get_by_id(occ.candidate_id) if occ is not None else None
        if occ is None or word is None:
            raise PhraseNotFoundError(occurrence_id)
        ensure_source_free(self._lock, word.source_id)
        is_cloze = export_kind(occ.card_state) is NoteKind.CLOZE
        if is_cloze and not self._decide_phrase.view(occurrence_id).can_edit_cloze:
            raise ClozeNotAllowedError(f"Phrase {occurrence_id} is already in Anki")

        if phrase != occ.phrase.text:
            raise ClozePhraseChangedError(occurrence_id)
        indices = tuple(sorted(set(hidden_word_indices)))
        self._builder.validate(occ.phrase, indices)
        custom = (custom_hint or "").strip()
        if hint_kind is ClozeHintKind.CUSTOM and not custom:
            raise InvalidClozeError("Write the hint")
        hidden = self._builder.hidden_words(occ.phrase, indices)
        if hint_kind not in self._builder.available_hints(occ.meaning, hidden):
            raise InvalidClozeError(
                f"The {hint_kind.value} hint is unavailable for the hidden words",
            )

        if not is_cloze:
            self._decide_phrase.press(occurrence_id, Press.CLOZE)
        self._cloze_repo.upsert_for_phrase(occurrence_id, CandidateCloze(
            candidate_id=occ.candidate_id,
            hidden_word_indices=indices,
            hint_kind=hint_kind,
            custom_hint=custom if hint_kind is ClozeHintKind.CUSTOM else None,
            phrase=phrase,
        ))
        return self._card_views.one(occurrence_id)
