from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import SyncResultDTO
from backend.application.utils.anki_note_builders import (
    ClozeNoteBuilder,
    NoteMedia,
    RecognitionNoteBuilder,
)
from backend.application.utils.anki_note_settings import AnkiNoteSettings
from backend.application.utils.anki_note_types import (
    AnkiNoteTypes,
    NoteTypeKind,
    is_app_note_type,
)
from backend.domain.exceptions import AnkiNotAvailableError, AnkiNoteTypeIncompleteError
from backend.domain.services.decision_rules import on_bind
from backend.domain.value_objects.source_scope import ScopeKind

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.application.utils.anki_note_types import NoteTypeCheck
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.application.utils.decision_effects import DecisionEffects
    from backend.application.utils.export_queue import ExportCard, ExportQueue
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.application.utils.user_vocabulary import UserVocabulary
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.services.cloze_builder import ClozeBuilder
    from backend.domain.value_objects.export_group import ExportGroup
    from backend.domain.value_objects.source_scope import SourceScope

_DEFAULT_DECK: str = "Default"


@dataclass(frozen=True)
class _NoteTarget:
    """Note type a card goes to and the field that holds its lemma (to find duplicates by)."""

    model_name: str
    target_field: str


@dataclass
class _Tally:
    added: int = 0
    skipped: int = 0
    errors: int = 0
    skipped_lemmas: list[str] = field(default_factory=list)
    error_lemmas: list[str] = field(default_factory=list)

    def skip(self, lemma: str) -> None:
        self.skipped += 1
        self.skipped_lemmas.append(lemma)

    def fail(self, lemma: str) -> None:
        self.errors += 1
        self.error_lemmas.append(lemma)


class SyncToAnkiUseCase:
    """Pushes one export group of the export queue to Anki via AnkiConnect.

    A cloze decision goes to the native cloze note type, the rest to the user's recognition
    note type; the note is made of the phrase of the decision. A note already in Anki is
    reused (`_find_existing`), so no duplicate is made. Then the card is bound to its note
    (S1, `on_bind`): its 30 days start now.
    """

    def __init__(
        self,
        export_queue: ExportQueue,
        anki_connector: AnkiConnector,
        settings_repo: SettingsRepository,
        template_renderer: AnkiTemplateRenderer,
        cloze_builder: ClozeBuilder,
        scope_resolver: SourceScopeResolver,
        vocabulary: UserVocabulary,
        effects: DecisionEffects,
    ) -> None:
        self._export_queue = export_queue
        self._connector = anki_connector
        self._settings_repo = settings_repo
        self._template_renderer = template_renderer
        self._vocabulary = vocabulary
        self._effects = effects
        self._cloze_builder = cloze_builder
        self._scope_resolver = scope_resolver

    def execute(self, scope: SourceScope, group: ExportGroup) -> SyncResultDTO:
        """Pushes the group of a set of sources: one source, a collection, Unsorted or all."""
        if scope.kind is ScopeKind.ALL:
            batch = self._export_queue.for_all()
        else:
            ids = {s.id for s in self._scope_resolver.sources(scope) if s.id is not None}
            batch = self._export_queue.for_sources(ids)
        return self._push(batch.in_group(group), group, f"scope={scope.token}")

    def _push(
        self, pending: list[ExportCard], group: ExportGroup, label: str,
    ) -> SyncResultDTO:
        deck_name = self._setting("anki_deck_name", _DEFAULT_DECK)
        total = len(pending)
        logger.info(
            "sync_to_anki: start (%s, group=%s, deck=%s, pending=%d)",
            label, group, deck_name, total,
        )
        if total == 0:
            return SyncResultDTO(total=0, added=0, skipped=0, errors=0)
        if not self._connector.is_available():
            raise AnkiNotAvailableError()

        settings = AnkiNoteSettings.read(self._settings_repo)
        fields = settings.fields
        plan = [(card, card.cloze_markup(self._cloze_builder)) for card in pending]
        note_types = AnkiNoteTypes(self._connector, self._template_renderer)
        used = {NoteTypeKind.CLOZE if cloze else NoteTypeKind.RECOGNITION for _, cloze in plan}
        for kind in (kind for kind in NoteTypeKind if kind in used):
            if is_app_note_type(kind, settings):
                note_types.ensure(kind, settings)
            _refuse_incomplete(note_types.check(kind, settings))
        self._connector.ensure_deck(deck_name)

        media = NoteMedia(self._connector)
        recognition = RecognitionNoteBuilder(fields, media)
        cloze_notes = ClozeNoteBuilder(self._cloze_builder, fields, media)
        recognition_target = _NoteTarget(settings.recognition_note_type, fields.target)
        cloze_target = _NoteTarget(settings.cloze_note_type, fields.target)

        tally = _Tally()
        with self._effects.batch():
            for card, cloze in plan:
                target = recognition_target if cloze is None else cloze_target
                try:
                    note = (
                        recognition.build(card) if cloze is None
                        else cloze_notes.build(card, cloze)
                    )
                    self._add(deck_name, target, card, note, tally)
                except AnkiNotAvailableError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    self._handle_failure(deck_name, target, card, exc, tally)

        logger.info(
            "sync_to_anki: done (%s, deck=%s, added=%d, skipped=%d, errors=%d)",
            label, deck_name, tally.added, tally.skipped, tally.errors,
        )
        return SyncResultDTO(
            total=total, added=tally.added, skipped=tally.skipped, errors=tally.errors,
            skipped_lemmas=tally.skipped_lemmas, error_lemmas=tally.error_lemmas,
        )

    def _add(
        self,
        deck_name: str,
        target: _NoteTarget,
        card: ExportCard,
        note: dict[str, str],
        tally: _Tally,
    ) -> None:
        results = self._connector.add_notes(
            deck_name=deck_name, model_name=target.model_name, notes=[note],
        )
        if results and results[0] is not None:
            self._mark_exported(card, results[0])
            tally.added += 1
            return
        # Note rejected (allowDuplicate=False) — check if it already exists
        existing = self._find_existing(deck_name, target, card.word)
        if existing is None:
            tally.fail(card.word.lemma)
            return
        self._mark_exported(card, existing)
        tally.skip(card.word.lemma)

    def _handle_failure(
        self,
        deck_name: str,
        target: _NoteTarget,
        card: ExportCard,
        exc: Exception,
        tally: _Tally,
    ) -> None:
        candidate = card.word
        if "duplicate" not in str(exc).lower():
            tally.fail(candidate.lemma)
            logger.exception(
                "sync_to_anki: candidate sync failed (candidate_id=%s, lemma=%s)",
                candidate.id, candidate.lemma,
            )
            return
        existing = self._find_existing(deck_name, target, candidate)
        if existing is None:
            tally.fail(candidate.lemma)
            logger.exception(
                "sync_to_anki: duplicate reported but no existing note "
                "(candidate_id=%s, lemma=%s)",
                candidate.id, candidate.lemma,
            )
            return
        self._mark_exported(card, existing)
        tally.skip(candidate.lemma)
        logger.info(
            "sync_to_anki: duplicate matched existing note "
            "(candidate_id=%s, lemma=%s, note_id=%s)",
            candidate.id, candidate.lemma, existing,
        )

    def _find_existing(
        self, deck_name: str, target: _NoteTarget, candidate: StoredCandidate
    ) -> int | None:
        existing = self._connector.find_notes_by_target(
            deck_name, target.model_name, target.target_field, candidate.lemma,
        )
        return existing[0] if existing else None

    def _mark_exported(self, card: ExportCard, note_id: int) -> None:
        """The card is bound to its note: the word is Learning, Known 30 days from now."""
        outcome = on_bind(
            card.state, card.phrase_id, self._vocabulary.of(card.word.lemma),
            self._vocabulary.scope.now,
        )
        self._effects.apply(card.state, outcome, card.word, note_id=note_id)

    def _setting(self, key: str, default: str) -> str:
        return self._settings_repo.get(key, default) or default


def _refuse_incomplete(check: NoteTypeCheck) -> None:
    """Anki drops the fields a note type lacks without a word, so such an export must not start."""
    if not check.ok:
        raise AnkiNoteTypeIncompleteError(
            check.note_type, list(check.missing_fields), exists=check.exists,
        )
