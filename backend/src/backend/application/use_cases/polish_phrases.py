from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from backend.application.utils.candidate_filter import CandidateFilter, keep_all
from backend.domain.exceptions import TargetNotInPhraseError
from backend.domain.value_objects.fragment_surroundings import FragmentSurroundings

if TYPE_CHECKING:
    from backend.application.utils.generation_targets import GenerationCard
    from backend.application.utils.job_phrases import JobPhrases
    from backend.application.utils.phrase_enrichment_reset import PhraseEnrichmentReset
    from backend.application.utils.rewrite_phrase import RewritePhrase
    from backend.application.utils.section_stamper import SectionStamper
    from backend.domain.entities.source import Source
    from backend.domain.ports.ai_service import AIService
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.ports.source_repository import SourceRepository
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.phrase_ref import PhraseRef
    from backend.domain.value_objects.prompts_config import PromptsConfig

logger = logging.getLogger(__name__)

POLISH_CONTEXT_CHARS = 500
DEFAULT_CEFR_LEVEL = "B1"
_BOLD_MARKERS = re.compile(r"\*{2}(.+?)\*{2}")
_WRAPPING_QUOTES = "\"'“”"


class PhrasePolishUseCase:
    """Asks AI to rewrite a batch of card phrases into easier ones and stores them.

    Runs in the worker. A phrase AI rewrote loses its meaning and TTS: they were made for
    the old text. An answer that lost the target is discarded and the source phrase stays.
    A phrase a Rebuild changed or deleted meanwhile gets nothing.
    """

    def __init__(
        self,
        job_phrases: JobPhrases,
        occurrence_repo: OccurrenceRepository,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        settings_repo: SettingsRepository,
        enrichment_reset: PhraseEnrichmentReset,
        ai_service: AIService,
        prompts_config: PromptsConfig,
        rewrite_phrase: RewritePhrase,
        stamper: SectionStamper,
    ) -> None:
        self._job_phrases = job_phrases
        self._occurrence_repo = occurrence_repo
        self._source_repo = source_repo
        self._document_repo = document_repo
        self._settings_repo = settings_repo
        self._enrichment_reset = enrichment_reset
        self._ai_service = ai_service
        self._prompts_config = prompts_config
        self._rewrite_phrase = rewrite_phrase
        self._stamper = stamper

    def execute_batch(
        self,
        phrases: list[PhraseRef],
        still_wanted: CandidateFilter = keep_all,
    ) -> list[int]:
        """Returns the wanted phrases AI gave no answer for."""
        waiting = [
            c for c in self._job_phrases.cards(phrases)
            if c.in_play and c.phrase.polished_phrase is None
        ]
        if not waiting:
            logger.info("PhrasePolish batch: nothing left to polish")
            return []

        sources: dict[int, Source | None] = {}
        for c in waiting:
            if c.word.source_id not in sources:
                sources[c.word.source_id] = self._source_repo.get_by_id(c.word.source_id)
        polishable = [
            c for c in waiting if (s := sources[c.word.source_id]) and s.can_polish_phrases
        ]
        if not polishable:
            return []

        documents = {
            source_id: self._document_repo.get(source_id)
            for source_id in {c.word.source_id for c in polishable}
        }
        batch_prompt = "\n\n".join(
            f"Phrase {i}:\n{self._phrase_prompt(c, documents[c.word.source_id])}"
            for i, c in enumerate(polishable, 1)
        )
        # Errors propagate -> worker marks the jobs failed for retry
        results = self._ai_service.polish_phrases_batch(self._system_prompt(), batch_prompt)
        by_index = {r.phrase_index: r.phrase for r in results}
        wanted = still_wanted([c.phrase_id for c in polishable])

        changed = 0
        unanswered: list[int] = []
        for i, c in enumerate(polishable, 1):
            if c.phrase_id not in wanted or not self._job_phrases.holds(c):
                continue
            answer = by_index.get(i)
            if answer is None:
                unanswered.append(c.phrase_id)
                continue
            if self._polish(c, answer) != c.phrase.phrase.text:
                self._enrichment_reset.reset_phrase(c.phrase_id)
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

    def _phrase_prompt(self, card: GenerationCard, document: Document | None) -> str:
        around = FragmentSurroundings.around(
            document, card.phrase.phrase_position, POLISH_CONTEXT_CHARS,
        )
        source = card.phrase.source_phrase
        context = f"{around.before}{source.text}{around.after}" if around else source.text
        return self._prompts_config.polish_phrase_user_template.format(
            lemma=card.word.lemma,
            pos=card.word.pos,
            surface_form=source.target_text(),
            phrase=source.text,
            context=" ".join(context.split()),
        )

    def _polish(self, card: GenerationCard, answer: str) -> str:
        """Stores AI's phrase and returns the text the card shows now. An answer that lost
        the target is discarded: the source phrase stays, marked as polished."""
        text = " ".join(_BOLD_MARKERS.sub(r"\1", answer).split()).strip(_WRAPPING_QUOTES)
        try:
            return self._rewrite_phrase.of_phrase(card.phrase, card.word, text).text
        except TargetNotInPhraseError:
            logger.warning(
                "PhrasePolish: answer lost the target, keeping the source phrase "
                "(phrase=%s, lemma=%r, answer=%r)",
                card.phrase_id, card.word.lemma, answer,
            )
            source = card.phrase.source_phrase
            self._occurrence_repo.write_text(
                card.phrase_id, source, card.phrase.phrase_position,
                earned_section=self._stamper.earned(source, card.word), polished=source,
            )
            return source.text
