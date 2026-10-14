from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.bootstrap_dtos import BootstrapWordDTO
from backend.domain.services.bootstrap_word_selector import BootstrapWordSelector
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.ports.bootstrap_index_repository import BootstrapIndexRepository
    from backend.domain.ports.settings_repository import SettingsRepository

_CEFR_ORDER = [CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1, CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2]


class GetBootstrapWordsUseCase:
    """Returns up to 15 words for the bootstrap calibration screen."""

    def __init__(
        self,
        index_repo: BootstrapIndexRepository,
        vocabulary: UserVocabulary,
        settings_repo: SettingsRepository,
    ) -> None:
        self._index_repo = index_repo
        self._vocabulary = vocabulary
        self._settings_repo = settings_repo

    def execute(self, excluded_lemmas: list[str]) -> list[BootstrapWordDTO]:
        user_cefr_str = self._settings_repo.get("cefr_level", "B1") or "B1"
        user_cefr = CEFRLevel.from_str(user_cefr_str)
        grid_levels = self._compute_grid_levels(user_cefr)

        if not grid_levels:
            return []

        entries = self._index_repo.get_all_entries()
        vocabulary = self._vocabulary.snapshot()
        decided_lemmas = set(vocabulary.known | vocabulary.unknown)

        selector = BootstrapWordSelector()
        selected = selector.select_words(
            entries=entries,
            grid_levels=grid_levels,
            known_lemmas=decided_lemmas,
            excluded_lemmas=set(excluded_lemmas),
        )

        return [
            BootstrapWordDTO(
                lemma=entry.lemma,
                cefr_level=entry.cefr_level.name,
                zipf_value=entry.zipf_value,
            )
            for entry in selected
        ]

    @staticmethod
    def _compute_grid_levels(user_level: CEFRLevel) -> set[CEFRLevel]:
        try:
            idx = _CEFR_ORDER.index(user_level)
        except ValueError:
            return set()
        above = _CEFR_ORDER[idx + 1 : idx + 4]
        return set(above)
