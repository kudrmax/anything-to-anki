from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import SyncResultDTO
from backend.application.use_cases.manage_settings import build_anki_field_map
from backend.application.utils.anki_note_builders import (
    CLOZE_FIELD_TARGET,
    CLOZE_FIELDS,
    CLOZE_NOTE_TYPE,
    AnkiFieldNames,
    ClozeNoteBuilder,
    NoteMedia,
    RecognitionNoteBuilder,
)
from backend.domain.exceptions import AnkiNotAvailableError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.application.utils.anki_template_renderer import AnkiTemplateRenderer
    from backend.application.utils.export_queue import ExportQueue
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.known_word_repository import KnownWordRepository
    from backend.domain.ports.settings_repository import SettingsRepository
    from backend.domain.services.cloze_builder import ClozeBuilder
    from backend.domain.value_objects.export_group import ExportGroup

_DEFAULT_NOTE_TYPE: str = "AnythingToAnkiType"
_DEFAULT_DECK: str = "Default"
_DEFAULT_FIELD_SENTENCE: str = "Sentence"
_DEFAULT_FIELD_TARGET: str = "Target"
_DEFAULT_FIELD_MEANING: str = "Meaning"
_DEFAULT_FIELD_IPA: str = "IPA"
_DEFAULT_FIELD_TRANSLATION: str = "Translation"
_DEFAULT_FIELD_SYNONYMS: str = "Synonyms"
_DEFAULT_FIELD_IMAGE: str = "Image"
_DEFAULT_FIELD_AUDIO: str = "Audio"
_DEFAULT_FIELD_EXAMPLES: str = "Examples"
_DEFAULT_FIELD_AUDIO_TARGET_US: str = "AudioTargetUS"
_DEFAULT_FIELD_AUDIO_TARGET_UK: str = "AudioTargetUK"
_DEFAULT_FIELD_AUDIO_TTS: str = "AudioTTS"


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
        note_type = self._setting("anki_note_type", _DEFAULT_NOTE_TYPE)
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

        fields = self._field_names()
        plan = [(candidate, self._cloze_builder.effective(candidate)) for candidate in pending]
        if any(cloze is None for _, cloze in plan):
            self._ensure_recognition_type(note_type, fields)
        if any(cloze is not None for _, cloze in plan):
            self._ensure_cloze_type()
        self._connector.ensure_deck(deck_name)

        media = NoteMedia(self._connector)
        recognition = RecognitionNoteBuilder(fields, media)
        cloze_notes = ClozeNoteBuilder(self._cloze_builder, media)
        recognition_target = _NoteTarget(note_type, fields.target)
        cloze_target = _NoteTarget(CLOZE_NOTE_TYPE, CLOZE_FIELD_TARGET)

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

    def _ensure_recognition_type(self, note_type: str, fields: AnkiFieldNames) -> None:
        """Only the app's own note type gets its templates; a user's own type is left as is."""
        if note_type != _DEFAULT_NOTE_TYPE:
            return
        field_map = build_anki_field_map({
            "anki_field_sentence": fields.sentence,
            "anki_field_target_word": fields.target,
            "anki_field_meaning": fields.meaning,
            "anki_field_ipa": fields.ipa,
            "anki_field_image": fields.image,
            "anki_field_audio": fields.audio,
            "anki_field_translation": fields.translation,
            "anki_field_synonyms": fields.synonyms,
            "anki_field_examples": fields.examples,
        })
        templates = self._template_renderer.render_all(field_map)
        self._connector.ensure_note_type(
            note_type,
            fields.in_order(),
            front_template=templates["front"],
            back_template=templates["back"],
            css=templates["css"],
        )

    def _ensure_cloze_type(self) -> None:
        templates = self._template_renderer.render_cloze()
        self._connector.ensure_note_type(
            CLOZE_NOTE_TYPE,
            list(CLOZE_FIELDS),
            front_template=templates["front"],
            back_template=templates["back"],
            css=templates["css"],
            is_cloze=True,
        )

    def _field_names(self) -> AnkiFieldNames:
        return AnkiFieldNames(
            sentence=self._setting("anki_field_sentence", _DEFAULT_FIELD_SENTENCE),
            target=self._setting("anki_field_target_word", _DEFAULT_FIELD_TARGET),
            meaning=self._setting("anki_field_meaning", _DEFAULT_FIELD_MEANING),
            ipa=self._setting("anki_field_ipa", _DEFAULT_FIELD_IPA),
            translation=self._setting("anki_field_translation", _DEFAULT_FIELD_TRANSLATION),
            synonyms=self._setting("anki_field_synonyms", _DEFAULT_FIELD_SYNONYMS),
            examples=self._setting("anki_field_examples", _DEFAULT_FIELD_EXAMPLES),
            image=self._setting("anki_field_image", _DEFAULT_FIELD_IMAGE),
            audio=self._setting("anki_field_audio", _DEFAULT_FIELD_AUDIO),
            audio_target_us=self._setting(
                "anki_field_audio_target_us", _DEFAULT_FIELD_AUDIO_TARGET_US
            ),
            audio_target_uk=self._setting(
                "anki_field_audio_target_uk", _DEFAULT_FIELD_AUDIO_TARGET_UK
            ),
            audio_tts=self._setting("anki_field_audio_tts", _DEFAULT_FIELD_AUDIO_TTS),
        )

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
