from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from backend.application.utils.candidate_filter import CandidateFilter, keep_all
from backend.domain.value_objects.candidate_status import CandidateStatus
from backend.domain.value_objects.fragment_surroundings import FragmentSurroundings

if TYPE_CHECKING:
    from backend.application.utils.phrase_enrichment_reset import PhraseEnrichmentReset
    from backend.domain.entities.source import Source
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.prompts_config import PromptsConfig

logger = logging.getLogger(__name__)

POLISH_CONTEXT_CHARS = 500
DEFAULT_CEFR_LEVEL = "B1"
_ACTIVE_STATUSES = frozenset({CandidateStatus.PENDING, CandidateStatus.LEARN})
_BOLD_MARKERS = re.compile(r"\*{2}(.+?)\*{2}")
_WRAPPING_QUOTES = "\"'“”"


class PhrasePolishUseCase:
    """Asks AI to rewrite a batch of card phrases into easier ones and stores them.

    Runs in the worker. A card whose phrase AI rewrote loses its meaning and TTS:
    they were made for the old phrase. An answer that lost the target is
    discarded and the source phrase stays.
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        source_repo: SourceRepository,
        settings_repo: SettingsRepository,
        enrichment_reset: PhraseEnrichmentReset,
        ai_service: AIService,
        prompts_config: PromptsConfig,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._source_repo = source_repo
        self._settings_repo = settings_repo
        self._enrichment_reset = enrichment_reset
        self._ai_service = ai_service
        self._prompts_config = prompts_config

    def execute_batch(
        self,
        candidate_ids: list[int],
        still_wanted: CandidateFilter = keep_all,
    ) -> list[int]:
        """Returns the wanted candidates AI gave no answer for."""
        waiting = [
            c for c in self._candidate_repo.get_by_ids(candidate_ids)
            if c.id is not None and c.status in _ACTIVE_STATUSES and c.polished_fragment is None
        ]
        if not waiting:
            logger.info("PhrasePolish batch: nothing left to polish")
            return []

        sources: dict[int, Source | None] = {}
        for c in waiting:
            if c.source_id not in sources:
                sources[c.source_id] = self._source_repo.get_by_id(c.source_id)
        polishable = [c for c in waiting if (s := sources[c.source_id]) and s.can_polish_phrases]
        if not polishable:
            return []

        batch_prompt = "\n\n".join(
            f"Phrase {i}:\n{self._phrase_prompt(c, sources[c.source_id])}"
            for i, c in enumerate(polishable, 1)
        )
        # Errors propagate -> worker marks the jobs failed for retry
        results = self._ai_service.polish_phrases_batch(self._system_prompt(), batch_prompt)
        by_index = {r.phrase_index: r.phrase for r in results}
        wanted = still_wanted([c.id for c in polishable if c.id is not None])

        changed = 0
        unanswered: list[int] = []
        for i, c in enumerate(polishable, 1):
            if c.id is None or c.id not in wanted:
                continue
            answer = by_index.get(i)
            if answer is None:
                unanswered.append(c.id)
                continue
            phrase = self._accepted_phrase(c, answer)
            self._candidate_repo.set_polished_fragment(c.id, phrase)
            if phrase != c.card_phrase:
                self._enrichment_reset.reset(c.id)
                changed += 1

        logger.info(
            "PhrasePolish batch: %d answered, %d changed of %d, %d still wanted",
            len(by_index), changed, len(polishable), len(wanted),
        )
        return unanswered

    def _system_prompt(self) -> str:
        cefr_level = (
            self._settings_repo.get("cefr_level", DEFAULT_CEFR_LEVEL) or DEFAULT_CEFR_LEVEL
        )
        return self._prompts_config.polish_phrase_system.format(cefr_level=cefr_level)

    def _phrase_prompt(self, candidate: StoredCandidate, source: Source | None) -> str:
        text = source.searchable_text if source else None
        around = (
            FragmentSurroundings.find(text, candidate.context_fragment, POLISH_CONTEXT_CHARS)
            if text else None
        )
        context = (
            f"{around.before}{candidate.context_fragment}{around.after}"
            if around else candidate.context_fragment
        )
        return self._prompts_config.polish_phrase_user_template.format(
            lemma=candidate.lemma,
            pos=candidate.pos,
            surface_form=candidate.surface_form or candidate.lemma,
            phrase=candidate.context_fragment,
            context=" ".join(context.split()),
        )

    @staticmethod
    def _accepted_phrase(candidate: StoredCandidate, answer: str) -> str:
        phrase = " ".join(_BOLD_MARKERS.sub(r"\1", answer).split()).strip(_WRAPPING_QUOTES)
        target = candidate.surface_form or candidate.lemma
        if not phrase or target.lower() not in phrase.lower():
            logger.warning(
                "PhrasePolish: answer lost the target, keeping the source phrase "
                "(candidate=%s, target=%r, answer=%r)",
                candidate.id, target, answer,
            )
            return candidate.context_fragment
        return phrase
