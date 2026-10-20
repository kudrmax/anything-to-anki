"""Words to learn with the phrases of their decisions, for export tests without a database.

A phrase id is never its word's id (`phrase_id_of`), so mixing the two fails a test.
"""
from __future__ import annotations

from collections.abc import Iterator  # noqa: TC003 — used at runtime by @contextmanager
from contextlib import contextmanager
from dataclasses import replace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from backend.application.use_cases.sync_to_anki import SyncToAnkiUseCase
from backend.application.utils.decision_effects import DecisionEffects
from backend.application.utils.export_queue import ExportCard, ExportQueue
from backend.domain.entities.occurrence import Occurrence
from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
from backend.domain.ports.word_state_repository import WordStateRepository
from backend.domain.services.card_view import stored_chosen_to_learn
from backend.domain.services.cloze_builder import ClozeBuilder
from backend.domain.value_objects.candidate_section import CandidateSection
from backend.domain.value_objects.card_choice import (
    Binding,
    CardChoice,
    CardState,
    NoteKind,
    WordState,
    export_kind,
)
from backend.domain.value_objects.phrase_origin_kind import (
    DecisionKind,
    OccurrenceOrigin,
    ShownBy,
)
from backend.domain.value_objects.word_status import WordStatus

from tests.decision_support import NOW
from tests.lock_support import free_lock
from tests.vocabulary_support import user_vocabulary
from tests.word_support import phrase_id_of

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable
    from datetime import datetime

    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.candidate_meaning import CandidateMeaning
    from backend.domain.entities.candidate_media import CandidateMedia
    from backend.domain.entities.candidate_tts import CandidateTTS
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.services.decision_rules import BindingRef
    from backend.domain.value_objects.anki_binding import AnkiBinding
    from backend.domain.value_objects.phrase import Phrase

_CHOICE_OF_KIND = {DecisionKind.LEARN: CardChoice.LEARN, DecisionKind.CLOZE: CardChoice.CLOZE}
_NOTE_OF_KIND = {DecisionKind.LEARN: NoteKind.LEARN, DecisionKind.CLOZE: NoteKind.CLOZE}


def export_card(
    word: StoredCandidate,
    text: Phrase,
    *,
    meaning: CandidateMeaning | None = None,
    media: CandidateMedia | None = None,
    tts: CandidateTTS | None = None,
    cloze: CandidateCloze | None = None,
    kind: DecisionKind | None = None,
    exported_at: datetime | None = None,
) -> ExportCard:
    """The word and the phrase of its decision. The decision is a cloze when the phrase has
    cloze markup, unless `kind` says otherwise. `exported_at`: the card is in Anki since
    then; its word is Learning."""
    assert word.id is not None
    if kind is None:
        kind = DecisionKind.CLOZE if cloze is not None else DecisionKind.LEARN
    binding = Binding(_NOTE_OF_KIND[kind], exported_at) if exported_at is not None else None
    chosen = word.status is not WordStatus.NEW
    if binding is not None:
        word = replace(word, status=WordStatus.LEARNING)
    phrase = Occurrence(
        id=phrase_id_of(word.id),
        candidate_id=word.id,
        origin=OccurrenceOrigin.AUTO,
        source_phrase=text,
        phrase_position=None,
        key=None,
        fragment_score=None, earned_section=CandidateSection.READY,
        shown_by=ShownBy.SELECTION,
        choice=_CHOICE_OF_KIND[kind] if chosen else CardChoice.NONE,
        binding=binding,
        meaning=meaning,
        media=media,
        tts=tts,
        cloze=cloze,
    )
    state = WordState(
        word.id, word.lemma, word.pos, word.source_id,
        (CardState(phrase_id_of(word.id), phrase.choice, binding),),
    )
    return ExportCard(word=word, phrase=phrase, state=state)


class ExportCards(WordStateRepository, AnkiSyncRepository):
    """The words, decision phrases and bindings the export reads and writes: `words`
    stands for the candidate repository; the object itself for the occurrence, word-state
    and Anki-sync repositories. `bindings`: what the export bound, in order."""

    def __init__(self) -> None:
        self._cards: list[ExportCard] = []
        self.bindings: list[AnkiBinding] = []
        self.saved: list[WordState] = []
        self.words = MagicMock()
        self.words.get_by_source.side_effect = lambda source_id: [
            c.word for c in self._cards if c.word.source_id == source_id
        ]
        self.words.chosen_to_learn.side_effect = self._chosen_to_learn

    def put(self, cards: Iterable[ExportCard]) -> None:
        """These cards and no others."""
        self._cards = list(cards)

    def decision_phrases(self, candidate_ids: list[int]) -> dict[int, Occurrence]:
        return {c.word_id: c.phrase for c in self._cards if c.word_id in candidate_ids}

    def queue(self) -> ExportQueue:
        return ExportQueue(self.words, self, self, user_vocabulary())  # type: ignore[arg-type]

    def sync(
        self,
        connector: AnkiConnector,
        settings_repo: SettingsRepository,
        template_renderer: AnkiTemplateRenderer,
        scope_resolver: SourceScopeResolver,
        vocabulary: UserVocabulary | None = None,
    ) -> SyncToAnkiUseCase:
        vocabulary = vocabulary or user_vocabulary()
        return SyncToAnkiUseCase(
            export_queue=ExportQueue(self.words, self, self, vocabulary),  # type: ignore[arg-type]
            anki_connector=connector,
            settings_repo=settings_repo,
            template_renderer=template_renderer,
            cloze_builder=ClozeBuilder(),
            scope_resolver=scope_resolver,
            vocabulary=vocabulary,
            effects=DecisionEffects(
                word_states=self, vocabulary=vocabulary, decision_repo=MagicMock(),
                anki_sync=self, lock=free_lock(),
            ),
            word_states=self,
            unit_of_work=MagicMock(),
        )

    def bound_notes(self) -> list[tuple[int, str, str | None]]:
        """(note id, lemma, POS) of every binding the export made."""
        return [(b.note_id, b.lemma, b.pos) for b in self.bindings]

    # ── WordStateRepository ────────────────────────────────────────────

    def of_word(self, word_id: int) -> WordState | None:
        return next((c.state for c in self._cards if c.word_id == word_id), None)

    def of_source(self, source_id: int) -> dict[int, WordState]:
        raise AssertionError("the export reads its words by id")

    def of_words(self, word_ids: Collection[int]) -> dict[int, WordState]:
        return {c.word_id: c.state for c in self._cards if c.word_id in word_ids}

    @contextmanager
    def batch(self) -> Iterator[None]:
        yield

    def of_lemma(self, lemma: str) -> list[WordState]:
        return [c.state for c in self._cards if c.word.lemma.lower() == lemma.lower()]

    def save(self, word: WordState) -> None:
        self.saved.append(word)

    # ── AnkiSyncRepository ─────────────────────────────────────────────

    def bind(self, binding: AnkiBinding) -> None:
        self.bindings.append(binding)

    def release(self, phrase_ids: Iterable[int], at: datetime) -> None:
        raise AssertionError("an export releases nothing")

    def release_rows(self, binding_ids: Iterable[int], at: datetime) -> None:
        raise AssertionError("an export releases nothing")

    def orphan(self, phrase_ids: Iterable[int]) -> None:
        raise AssertionError("an export deletes no card")

    def orphan_source(self, source_id: int) -> None:
        raise AssertionError("an export deletes no source")

    def orphans(self, lemma: str) -> list[BindingRef]:
        return []

    def _chosen_to_learn(self, source_ids: Collection[int] | None) -> list[StoredCandidate]:
        return [
            c.word for c in self._cards
            if stored_chosen_to_learn(c.word.status)
            and (source_ids is None or c.word.source_id in source_ids)
        ]


def _decision_kind(phrase: Occurrence) -> DecisionKind | None:
    kind = export_kind(phrase.card_state)
    return DecisionKind(kind.value) if kind is not None else None


def in_anki(card: ExportCard) -> ExportCard:
    """The card as an earlier export left it: bound to its note, its word Learning."""
    return export_card(
        card.word, card.phrase.source_phrase, meaning=card.phrase.meaning,
        media=card.phrase.media, tts=card.phrase.tts, cloze=card.phrase.cloze,
        kind=_decision_kind(card.phrase), exported_at=NOW,
    )


def with_phrase(card: ExportCard, **changes: object) -> ExportCard:
    """The card with its decision phrase changed."""
    return replace(card, phrase=replace(card.phrase, **changes))  # type: ignore[arg-type]


def with_word(card: ExportCard, **changes: object) -> ExportCard:
    """The card with its word changed."""
    return replace(card, word=replace(card.word, **changes))  # type: ignore[arg-type]
