from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.application.dto.bootstrap_dtos import BootstrapStatusDTO
from backend.domain.entities.bootstrap_word_entry import BootstrapWordEntry
from backend.domain.value_objects.bootstrap_index_status import BootstrapIndexStatus
from backend.domain.value_objects.cefr_level import CEFRLevel

if TYPE_CHECKING:
    from backend.domain.ports.bootstrap_index_repository import BootstrapIndexRepository
    from backend.domain.ports.cefr_classifier import CEFRClassifier
    from backend.domain.ports.frequency_provider import FrequencyProvider
    from backend.domain.ports.phrasal_verb_dictionary import PhrasalVerbDictionary
    from backend.domain.ports.unit_of_work import UnitOfWork
    from backend.domain.ports.word_corpus_provider import WordCorpusProvider

logger = logging.getLogger(__name__)

_ZIPF_MIN = 3.0
_ZIPF_MAX = 5.5


def _is_multi_word(lemma: str) -> bool:
    """Multi-word or hyphenated lemmas (e.g. 'police station', 'brother-in-law')
    are skipped because the pipeline tokenizes text into single tokens
    and cannot match them."""
    return " " in lemma or "-" in lemma


class BuildBootstrapIndexUseCase:
    """Builds the bootstrap calibration index from the word corpus, in one write
    transaction."""

    def __init__(
        self,
        corpus_provider: WordCorpusProvider,
        cefr_classifier: CEFRClassifier,
        frequency_provider: FrequencyProvider,
        index_repo: BootstrapIndexRepository,
        phrasal_verb_dictionary: PhrasalVerbDictionary,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._corpus_provider = corpus_provider
        self._cefr_classifier = cefr_classifier
        self._frequency_provider = frequency_provider
        self._index_repo = index_repo
        self._phrasal_verb_dictionary = phrasal_verb_dictionary

    def status(self) -> BootstrapStatusDTO:
        meta = self._index_repo.get_meta()
        return BootstrapStatusDTO(
            status=meta.status.value,
            error=meta.error,
            built_at=meta.built_at,
            word_count=meta.word_count,
        )

    def is_building(self) -> bool:
        return self._index_repo.get_meta().status is BootstrapIndexStatus.BUILDING

    def execute(self) -> None:
        with self._unit_of_work.write():
            self._build()

    def _build(self) -> None:
        self._index_repo.set_meta(status=BootstrapIndexStatus.BUILDING)
        try:
            entries = self._build_entries()
            self._index_repo.rebuild(entries)
            self._index_repo.set_meta(
                status=BootstrapIndexStatus.READY,
                word_count=len(entries),
                built_at=datetime.now(tz=UTC),
            )
        except Exception as e:
            logger.exception("Bootstrap index build failed")
            self._index_repo.set_meta(
                status=BootstrapIndexStatus.ERROR,
                error=str(e),
            )

    def _build_entries(self) -> list[BootstrapWordEntry]:
        pairs = self._corpus_provider.get_all_lemma_pos_pairs()

        lemma_cefr_levels: dict[str, set[CEFRLevel]] = {}
        for lemma, pos in pairs:
            if _is_multi_word(lemma) or self._phrasal_verb_dictionary.contains_phrase(lemma):
                continue
            try:
                cefr = self._cefr_classifier.classify(lemma, pos)
            except Exception:
                logger.debug("Failed to classify %r/%r, skipping", lemma, pos)
                continue
            if cefr is CEFRLevel.UNKNOWN:
                continue
            lemma_cefr_levels.setdefault(lemma, set()).add(cefr)

        entries: list[BootstrapWordEntry] = []
        for lemma, cefr_levels in lemma_cefr_levels.items():
            zipf = self._frequency_provider.get_zipf_value(lemma)
            if zipf < _ZIPF_MIN or zipf > _ZIPF_MAX:
                continue
            for cefr in cefr_levels:
                entries.append(BootstrapWordEntry(lemma=lemma, cefr_level=cefr, zipf_value=zipf))

        return entries
