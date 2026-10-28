from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.bootstrap_dtos import BootstrapWordDTO
from backend.application.utils.saved_level import saved_level
from backend.domain.services.bootstrap_word_selector import BootstrapWordSelector
from backend.domain.services.review_order_word_selector import ReviewOrderWordSelector
from backend.domain.value_objects.calibration_order import CalibrationOrder
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.application.utils.frequent_word_threshold_resolver import (
        FrequentWordThresholdResolver,
    )
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
    from backend.domain.ports.bootstrap_index_repository import BootstrapIndexRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.word_corpus_provider import WordCorpusProvider

_CEFR_ORDER = [CEFRLevel.A1, CEFRLevel.A2, CEFRLevel.B1, CEFRLevel.B2, CEFRLevel.C1, CEFRLevel.C2]
GRID_LEVELS = 3
ROUND_SIZE = 15


class GetBootstrapWordsUseCase:
    """Returns up to 15 words for the bootstrap calibration screen, in the order asked."""

    def __init__(
        self,
        index_repo: BootstrapIndexRepository,
        vocabulary: UserVocabulary,
        settings_repo: SettingsRepository,
        threshold_resolver: FrequentWordThresholdResolver,
        corpus_provider: WordCorpusProvider,
    ) -> None:
        self._index_repo = index_repo
        self._vocabulary = vocabulary
        self._settings_repo = settings_repo
        self._threshold_resolver = threshold_resolver
        self._corpus_provider = corpus_provider

    def execute(
        self, excluded_lemmas: list[str], order: CalibrationOrder = CalibrationOrder.REVIEW,
    ) -> list[BootstrapWordDTO]:
        vocabulary = self._vocabulary.snapshot()
        decided_lemmas = set(vocabulary.known | vocabulary.unknown | vocabulary.learning)
        if order is CalibrationOrder.REVIEW:
            selected = self._in_review_order(decided_lemmas, set(excluded_lemmas))
        else:
            selected = self._spread(decided_lemmas, set(excluded_lemmas))
        return [
            BootstrapWordDTO(
                lemma=entry.lemma,
                cefr_level=entry.cefr_level.name,
                zipf_value=entry.zipf_value,
            )
            for entry in selected
        ]

    def _in_review_order(
        self, decided_lemmas: set[str], excluded_lemmas: set[str],
    ) -> list[BootstrapWordEntry]:
        return ReviewOrderWordSelector().select_words(
            entries=self._index_repo.get_all_entries(),
            user_level=saved_level(self._settings_repo),
            frequent_zipf=self._threshold_resolver.resolve().zipf,
            decided_lemmas=decided_lemmas,
            excluded_lemmas=excluded_lemmas,
            limit=ROUND_SIZE,
            dictionary_lemmas=self._dictionary_lemmas(),
        )

    def _dictionary_lemmas(self) -> set[str]:
        return {lemma for lemma, _ in self._corpus_provider.get_all_lemma_pos_pairs()}

    def _spread(
        self, decided_lemmas: set[str], excluded_lemmas: set[str],
    ) -> list[BootstrapWordEntry]:
        grid_levels = self._compute_grid_levels(saved_level(self._settings_repo))
        if not grid_levels:
            return []
        return BootstrapWordSelector().select_words(
            entries=self._index_repo.get_all_entries(),
            grid_levels=grid_levels,
            known_lemmas=decided_lemmas,
            excluded_lemmas=excluded_lemmas,
        )

    @staticmethod
    def _compute_grid_levels(user_level: CEFRLevel) -> set[CEFRLevel]:
        """The user's level and the ones above it, GRID_LEVELS in all at most."""
        try:
            idx = _CEFR_ORDER.index(user_level)
        except ValueError:
            return set()
        return set(_CEFR_ORDER[idx : idx + GRID_LEVELS])
