from __future__ import annotations

from typing import TYPE_CHECKING

from backend.domain.entities.occurrence import Occurrence
from backend.domain.services.rebuild_plan import SectionChange
from backend.domain.value_objects.built_analysis import WordKey
from backend.domain.value_objects.card_choice import Press, is_skipped
from backend.domain.value_objects.phrase_origin_kind import OccurrenceOrigin, ShownBy

if TYPE_CHECKING:
    from backend.application.use_cases.decide_phrase import DecidePhraseUseCase
    from backend.application.utils.section_stamper import SectionStamper
    from backend.domain.entities.occurrence import OccurrenceKey
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.occurrence_repository import OccurrenceRepository
    from backend.domain.value_objects.new_card import NewCard
    from backend.domain.value_objects.phrase import Phrase


class ManualPhrases:
    """A phrase the user made a card of, stored as a phrase of its target's word.

    A word the source already has gets another phrase; at the place of one of its auto
    phrases, or of a manual phrase with the same text, that phrase is shown instead of a
    duplicate, unless the user removed its card (and if it was the selection card, it keeps
    standing for it; a skipped one is unskipped by pressing Skip, unless its word is
    decided elsewhere: then it stays done).
    """

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        occurrence_repo: OccurrenceRepository,
        stamper: SectionStamper,
        decide_phrase: DecidePhraseUseCase,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._occurrences = occurrence_repo
        self._stamper = stamper
        self._decide_phrase = decide_phrase

    def show(
        self,
        card: NewCard,
        key: OccurrenceKey | None,
        polished: Phrase | None = None,
        instead_of: int | None = None,
    ) -> int:
        """The shown phrase of `card`, at `key` in the document; `polished`: the text the
        card shows instead of its phrase, final as it is; `instead_of`: the phrase the new
        one replaces. Returns the phrase."""
        word_id = self._word_of(card.word)
        if word_id is None:
            word_id = self._candidate_repo.add_word(card.word)
            return self._add(word_id, card, key, polished)
        existing = self._at(word_id, card, key, instead_of)
        if existing is None:
            return self._add(word_id, card, key, polished)
        return self._show_existing(existing, card, polished)

    def _word_of(self, word: StoredCandidate) -> int | None:
        return self._candidate_repo.word_id(
            word.source_id, WordKey.of(word.lemma, word.is_phrasal_verb),
        )

    def _at(
        self, word_id: int, card: NewCard, key: OccurrenceKey | None, instead_of: int | None,
    ) -> Occurrence | None:
        if key is None:
            return None
        return next(
            (
                o for o in self._occurrences.of_word(word_id)
                if o.key == key and o.id != instead_of and not o.removed_by_user and (
                    o.origin is OccurrenceOrigin.AUTO
                    or (
                        o.origin is OccurrenceOrigin.MANUAL
                        and o.source_phrase.text == card.phrase.text
                    )
                )
            ),
            None,
        )

    def _show_existing(
        self, existing: Occurrence, card: NewCard, polished: Phrase | None,
    ) -> int:
        assert existing.id is not None
        if existing.shown_by is ShownBy.SELECTION:
            self._occurrences.set_replaces_selection(existing.id, True)
        self._occurrences.set_shown([existing.id], ShownBy.USER)
        shown = polished or existing.phrase
        if polished is not None and polished.text != existing.phrase.text:
            self._occurrences.write_text(
                existing.id, existing.source_phrase, existing.phrase_position,
                earned_section=self._stamper.earned(polished, card.word), polished=polished,
            )
        else:
            self._occurrences.set_earned_sections([SectionChange(
                occurrence_id=existing.id,
                earned_section=self._stamper.earned(shown, card.word),
            )])
        if is_skipped(existing.card_state):
            self._decide_phrase.press_unless_done(existing.id, Press.SKIP)
        return existing.id

    def _add(
        self, word_id: int, card: NewCard, key: OccurrenceKey | None, polished: Phrase | None,
    ) -> int:
        added = self._occurrences.add(Occurrence(
            candidate_id=word_id,
            origin=OccurrenceOrigin.MANUAL,
            source_phrase=card.phrase,
            phrase_position=card.position,
            key=key,
            fragment_score=None,
            earned_section=self._stamper.earned(polished or card.phrase, card.word),
            shown_by=ShownBy.USER,
            polished_phrase=polished,
        ))
        assert added.id is not None
        return added.id
