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

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.application.utils.anki_note_types import NoteTypeCheck
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.application.utils.export_queue import ExportQueue
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.known_word_repository import KnownWordRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.services.cloze_builder import ClozeBuilder
    from backend.domain.value_objects.export_group import ExportGroup

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
    """Pushes one export group of not yet exported 'learn' candidates to Anki via AnkiConnect.

    A candidate with cloze markup goes to the native cloze note type, the rest
    to the user's recognition note type.
    """

    def __init__(
        self,
        export_queue: ExportQueue,
        anki_connector: AnkiConnector,
        settings_repo: SettingsRepository,
        anki_sync_repo: AnkiSyncRepository,
        template_renderer: AnkiTemplateRenderer,
        known_word_repo: KnownWordRepository,
        cloze_builder: ClozeBuilder,
    ) -> None:
        self._export_queue = export_queue
        self._connector = anki_connector
        self._settings_repo = settings_repo
        self._anki_sync_repo = anki_sync_repo
        self._template_renderer = template_renderer
        self._known_word_repo = known_word_repo
        self._cloze_builder = cloze_builder

    def execute(self, source_id: int, group: ExportGroup) -> SyncResultDTO:
        deck_name = self._setting("anki_deck_name", _DEFAULT_DECK)
        pending = self._export_queue.for_source(source_id).in_group(group)

        total = len(pending)
        logger.info(
            "sync_to_anki: start (source_id=%d, group=%s, deck=%s, pending=%d)",
            source_id, group, deck_name, total,
        )
        if total == 0:
            return SyncResultDTO(total=0, added=0, skipped=0, errors=0)

        if not self._connector.is_available():
            raise AnkiNotAvailableError()

        settings = AnkiNoteSettings.read(self._settings_repo)
        fields = settings.fields
        plan = [(candidate, self._cloze_builder.effective(candidate)) for candidate in pending]
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
        for candidate, cloze in plan:
            target = recognition_target if cloze is None else cloze_target
            try:
                note = (
                    recognition.build(candidate)
                    if cloze is None
                    else cloze_notes.build(candidate, cloze)
                )
                self._add(deck_name, target, candidate, note, tally)
            except AnkiNotAvailableError:
                raise
            except Exception as exc:  # noqa: BLE001
                self._handle_failure(deck_name, target, candidate, exc, tally)

        logger.info(
            "sync_to_anki: done (source_id=%d, deck=%s, added=%d, skipped=%d, errors=%d)",
            source_id, deck_name, tally.added, tally.skipped, tally.errors,
        )
        return SyncResultDTO(
            total=total, added=tally.added, skipped=tally.skipped, errors=tally.errors,
            skipped_lemmas=tally.skipped_lemmas, error_lemmas=tally.error_lemmas,
        )

    def _add(
        self,
        deck_name: str,
        target: _NoteTarget,
        candidate: StoredCandidate,
        note: dict[str, str],
        tally: _Tally,
    ) -> None:
        results = self._connector.add_notes(
            deck_name=deck_name, model_name=target.model_name, notes=[note],
        )
        if results and results[0] is not None:
            self._mark_exported(candidate, results[0])
            tally.added += 1
            return
        # Note rejected (allowDuplicate=False) — check if it already exists
        existing = self._find_existing(deck_name, target, candidate)
        if existing is None:
            tally.fail(candidate.lemma)
            return
        self._mark_exported(candidate, existing)
        tally.skip(candidate.lemma)

    def _handle_failure(
        self,
        deck_name: str,
        target: _NoteTarget,
        candidate: StoredCandidate,
        exc: Exception,
        tally: _Tally,
    ) -> None:
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
        self._mark_exported(candidate, existing)
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

    def _mark_exported(self, candidate: StoredCandidate, note_id: int) -> None:
        self._anki_sync_repo.mark_synced(candidate.id, note_id)  # type: ignore[arg-type]
        self._known_word_repo.add(candidate.lemma, candidate.pos)

    def _setting(self, key: str, default: str) -> str:
        return self._settings_repo.get(key, default) or default

    def execute_all(self, group: ExportGroup) -> SyncResultDTO:
        """Sync the group's not yet exported learn candidates of every source to Anki."""
        pending = self._export_queue.for_all().in_group(group)
        if not pending:
            return SyncResultDTO(total=0, added=0, skipped=0, errors=0)

        source_ids = list(dict.fromkeys(c.source_id for c in pending))

        total = 0
        added = 0
        skipped = 0
        errors = 0
        skipped_lemmas: list[str] = []
        error_lemmas: list[str] = []

        for source_id in source_ids:
            result = self.execute(source_id, group)
            total += result.total
            added += result.added
            skipped += result.skipped
            errors += result.errors
            skipped_lemmas.extend(result.skipped_lemmas)
            error_lemmas.extend(result.error_lemmas)

        return SyncResultDTO(
            total=total,
            added=added,
            skipped=skipped,
            errors=errors,
            skipped_lemmas=skipped_lemmas,
            error_lemmas=error_lemmas,
        )


def _refuse_incomplete(check: NoteTypeCheck) -> None:
    """Anki drops the fields a note type lacks without a word, so such an export must not start."""
    if not check.ok:
        raise AnkiNoteTypeIncompleteError(
            check.note_type, list(check.missing_fields), exists=check.exists,
        )
