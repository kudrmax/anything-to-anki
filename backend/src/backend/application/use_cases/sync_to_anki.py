from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.application.dto.anki_dtos import SyncResultDTO
from backend.application.utils.highlight import highlight_all_forms
from backend.domain.exceptions import AnkiNotAvailableError
from backend.domain.value_objects.candidate_status import CandidateStatus

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.ports.anki_sync_repository import AnkiSyncRepository
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.settings_repository import SettingsRepository

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


class SyncToAnkiUseCase:
    """Generates Anki cards for 'learn' candidates and pushes them via AnkiConnect."""

    def __init__(
        self,
        candidate_repo: CandidateRepository,
        anki_connector: AnkiConnector,
        settings_repo: SettingsRepository,
        anki_sync_repo: AnkiSyncRepository,
    ) -> None:
        self._candidate_repo = candidate_repo
        self._connector = anki_connector
        self._settings_repo = settings_repo
        self._anki_sync_repo = anki_sync_repo

    def execute(self, source_id: int) -> SyncResultDTO:
        deck_name = self._settings_repo.get("anki_deck_name", _DEFAULT_DECK) or _DEFAULT_DECK
        note_type = (
            self._settings_repo.get("anki_note_type", _DEFAULT_NOTE_TYPE) or _DEFAULT_NOTE_TYPE
        )
        field_sentence = (
            self._settings_repo.get("anki_field_sentence", _DEFAULT_FIELD_SENTENCE)
            or _DEFAULT_FIELD_SENTENCE
        )
        field_target = (
            self._settings_repo.get("anki_field_target_word", _DEFAULT_FIELD_TARGET)
            or _DEFAULT_FIELD_TARGET
        )
        field_meaning = (
            self._settings_repo.get("anki_field_meaning", _DEFAULT_FIELD_MEANING)
            or _DEFAULT_FIELD_MEANING
        )
        field_ipa = (
            self._settings_repo.get("anki_field_ipa", _DEFAULT_FIELD_IPA) or _DEFAULT_FIELD_IPA
        )
        field_image = (
            self._settings_repo.get("anki_field_image", _DEFAULT_FIELD_IMAGE)
            or _DEFAULT_FIELD_IMAGE
        )
        field_audio = (
            self._settings_repo.get("anki_field_audio", _DEFAULT_FIELD_AUDIO)
            or _DEFAULT_FIELD_AUDIO
        )
        field_translation = (
            self._settings_repo.get("anki_field_translation", _DEFAULT_FIELD_TRANSLATION)
            or _DEFAULT_FIELD_TRANSLATION
        )
        field_synonyms = (
            self._settings_repo.get("anki_field_synonyms", _DEFAULT_FIELD_SYNONYMS)
            or _DEFAULT_FIELD_SYNONYMS
        )
        field_examples = (
            self._settings_repo.get("anki_field_examples", _DEFAULT_FIELD_EXAMPLES)
            or _DEFAULT_FIELD_EXAMPLES
        )

        candidates = self._candidate_repo.get_by_source(source_id)
        learn_candidates = [c for c in candidates if c.status == CandidateStatus.LEARN]

        total = len(learn_candidates)
        logger.info(
            "sync_to_anki: start (source_id=%d, deck=%s, learn_candidates=%d)",
            source_id, deck_name, total,
        )
        if total == 0:
            return SyncResultDTO(total=0, added=0, skipped=0, errors=0)

        if not self._connector.is_available():
            raise AnkiNotAvailableError()

        candidate_ids = [c.id for c in learn_candidates if c.id is not None]
        already_synced = self._anki_sync_repo.get_synced_candidate_ids(candidate_ids)
        pending = [c for c in learn_candidates if c.id not in already_synced]
        skipped = len(learn_candidates) - len(pending)
        skipped_lemmas: list[str] = [c.lemma for c in learn_candidates if c.id in already_synced]

        if not pending:
            return SyncResultDTO(
                total=total, added=0, skipped=skipped, errors=0,
                skipped_lemmas=skipped_lemmas,
            )

        active_fields = [
            f for f in [
                field_sentence, field_target, field_meaning, field_ipa,
                field_translation, field_synonyms, field_examples,
                field_image, field_audio,
            ]
            if f
        ]
        if note_type == _DEFAULT_NOTE_TYPE:
            self._connector.ensure_note_type(note_type, active_fields)
        self._connector.ensure_deck(deck_name)

        added = 0
        errors = 0
        error_lemmas: list[str] = []

        for candidate in pending:
            try:
                sentence = highlight_all_forms(
                    candidate.context_fragment,
                    candidate.lemma,
                    candidate.surface_form,
                )
                meaning_text = candidate.meaning.meaning if candidate.meaning else None
                meaning = (
                    highlight_all_forms(
                        meaning_text,
                        candidate.lemma,
                        candidate.surface_form,
                    )
                    if meaning_text
                    else ""
                )

                note: dict[str, str] = {}
                if field_sentence:
                    note[field_sentence] = sentence
                if field_target:
                    note[field_target] = candidate.lemma
                if field_meaning:
                    note[field_meaning] = meaning
                if field_ipa:
                    note[field_ipa] = (candidate.meaning.ipa if candidate.meaning else None) or ""
                if (
                    field_translation
                    and candidate.meaning
                    and candidate.meaning.translation
                ):
                    note[field_translation] = highlight_all_forms(
                        candidate.meaning.translation,
                        candidate.lemma,
                        candidate.surface_form,
                    )
                if (
                    field_synonyms
                    and candidate.meaning
                    and candidate.meaning.synonyms
                ):
                    note[field_synonyms] = highlight_all_forms(
                        candidate.meaning.synonyms,
                        candidate.lemma,
                        candidate.surface_form,
                    )
                if (
                    field_examples
                    and candidate.meaning
                    and candidate.meaning.examples
                ):
                    note[field_examples] = highlight_all_forms(
                        candidate.meaning.examples,
                        candidate.lemma,
                        candidate.surface_form,
                    )
                if (
                    field_image
                    and candidate.media
                    and candidate.media.screenshot_path
                    and os.path.exists(candidate.media.screenshot_path)
                ):
                    filename = os.path.basename(candidate.media.screenshot_path)
                    self._connector.store_media_file(filename, candidate.media.screenshot_path)
                    note[field_image] = f'<img src="{filename}">'
                if (
                    field_audio
                    and candidate.media
                    and candidate.media.audio_path
                    and os.path.exists(candidate.media.audio_path)
                ):
                    filename = os.path.basename(candidate.media.audio_path)
                    self._connector.store_media_file(filename, candidate.media.audio_path)
                    note[field_audio] = f'[sound:{filename}]'

                results = self._connector.add_notes(
                    deck_name=deck_name,
                    model_name=note_type,
                    notes=[note],
                )
                if results and results[0] is not None:
                    self._anki_sync_repo.mark_synced(candidate.id, results[0])  # type: ignore[arg-type]
                    added += 1
                else:
                    # Note rejected (allowDuplicate=False) — check if it already exists
                    existing = self._connector.find_notes_by_target(deck_name, candidate.lemma)
                    if existing:
                        self._anki_sync_repo.mark_synced(candidate.id, existing[0])  # type: ignore[arg-type]
                        skipped += 1
                        skipped_lemmas.append(candidate.lemma)
                    else:
                        errors += 1
                        error_lemmas.append(candidate.lemma)
            except AnkiNotAvailableError:
                raise
            except Exception as exc:  # noqa: BLE001
                if "duplicate" in str(exc).lower():
                    existing = self._connector.find_notes_by_target(deck_name, candidate.lemma)
                    if existing:
                        self._anki_sync_repo.mark_synced(candidate.id, existing[0])  # type: ignore[arg-type]
                        skipped += 1
                        skipped_lemmas.append(candidate.lemma)
                        logger.info(
                            "sync_to_anki: duplicate matched existing note "
                            "(candidate_id=%s, lemma=%s, note_id=%s)",
                            candidate.id, candidate.lemma, existing[0],
                        )
                    else:
                        errors += 1
                        error_lemmas.append(candidate.lemma)
                        logger.exception(
                            "sync_to_anki: duplicate reported but no existing note "
                            "(candidate_id=%s, lemma=%s)",
                            candidate.id, candidate.lemma,
                        )
                else:
                    errors += 1
                    error_lemmas.append(candidate.lemma)
                    logger.exception(
                        "sync_to_anki: candidate sync failed "
                        "(candidate_id=%s, lemma=%s)",
                        candidate.id, candidate.lemma,
                    )

        logger.info(
            "sync_to_anki: done (source_id=%d, deck=%s, added=%d, skipped=%d, errors=%d)",
            source_id, deck_name, added, skipped, errors,
        )
        return SyncResultDTO(
            total=total, added=added, skipped=skipped, errors=errors,
            skipped_lemmas=skipped_lemmas, error_lemmas=error_lemmas,
        )
