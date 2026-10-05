from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.application.constants import CLOZE_DEFAULT_HINT_SETTING, DEFAULT_CLOZE_HINT
from backend.application.dto.cloze_dtos import ClozePreviewDTO, ClozeWordDTO
from backend.domain.exceptions import CandidateNotFoundError
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

if TYPE_CHECKING:
    from backend.application.dto.cloze_dtos import PreviewClozeRequest
    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.services.cloze_builder import ClozeBuilder, ClozeWord

logger = logging.getLogger(__name__)


class PreviewClozeUseCase:
    """Shows how the cloze card would look while the user picks the words to hide.

    Whatever the request leaves out comes from the saved markup, then from the defaults:
    the target words hidden and the hint from the settings.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        settings_repo: SettingsRepository,
        builder: ClozeBuilder,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._settings_repo = settings_repo
        self._builder = builder

    def execute(self, candidate_id: int, request: PreviewClozeRequest) -> ClozePreviewDTO:
        candidate = self._candidate_repo.get_by_id(candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(candidate_id)
        saved = self._builder.effective(candidate)
        phrase = candidate.card_phrase
        words = self._builder.words(phrase, candidate.lemma, candidate.surface_form)

        indices = self._indices(request, saved, words)
        if indices:
            self._builder.validate(words, indices)
        hidden = self._builder.hidden_words(phrase, indices)
        available = self._builder.available_hints(candidate.meaning, hidden)
        kind = self._hint_kind(request, saved)
        if kind not in available:
            kind = ClozeHintKind.NONE
        custom = request.custom_hint
        if custom is None and saved is not None:
            custom = saved.custom_hint

        return ClozePreviewDTO(
            words=[ClozeWordDTO(index=w.index, text=w.text, is_target=w.is_target) for w in words],
            hidden_word_indices=list(indices),
            hint_kind=kind.value,
            custom_hint=custom,
            front=self._builder.front_preview(phrase, indices),
            hint=self._builder.hint_text(kind, candidate.meaning, hidden, custom),
            available_hints=[k.value for k in available],
        )

    def _indices(
        self,
        request: PreviewClozeRequest,
        saved: CandidateCloze | None,
        words: list[ClozeWord],
    ) -> tuple[int, ...]:
        if request.hidden_word_indices is not None:
            return tuple(sorted(set(request.hidden_word_indices)))
        if saved is not None:
            return saved.hidden_word_indices
        return self._builder.default_hidden(words)

    def _hint_kind(
        self, request: PreviewClozeRequest, saved: CandidateCloze | None,
    ) -> ClozeHintKind:
        if request.hint_kind is not None:
            return ClozeHintKind(request.hint_kind)
        if saved is not None:
            return saved.hint_kind
        default = self._settings_repo.get(CLOZE_DEFAULT_HINT_SETTING, DEFAULT_CLOZE_HINT)
        try:
            return ClozeHintKind(default or DEFAULT_CLOZE_HINT)
        except ValueError:
            logger.warning("Unknown cloze_default_hint setting %r, using none", default)
            return ClozeHintKind.NONE
