from __future__ import annotations

import os
from typing import TYPE_CHECKING

from backend.application.utils.highlight import format_examples_as_list, highlight_all_forms
from backend.domain.value_objects.cloze_hint_kind import ClozeHintKind

if TYPE_CHECKING:
    from collections.abc import Callable

    from backend.application.utils.anki_note_settings import AnkiFieldNames
    from backend.domain.entities.candidate_cloze import CandidateCloze
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.anki_connector import AnkiConnector
    from backend.domain.services.cloze_builder import ClozeBuilder

class NoteMedia:
    """Copies a candidate's local media files into Anki and returns the field markup for them."""

    def __init__(self, connector: AnkiConnector) -> None:
        self._connector = connector

    def image(self, path: str | None) -> str | None:
        filename = self._store(path)
        return f'<img src="{filename}">' if filename else None

    def sound(self, path: str | None) -> str | None:
        filename = self._store(path)
        return f"[sound:{filename}]" if filename else None

    def _store(self, path: str | None) -> str | None:
        if not path or not os.path.exists(path):
            return None
        filename = os.path.basename(path)
        self._connector.store_media_file(filename, path)
        return filename


class _CardContent:
    """Fills the parts every card type shares: target, meaning, translations, examples, media."""

    def __init__(self, fields: AnkiFieldNames, media: NoteMedia) -> None:
        self._fields = fields
        self._media = media

    def fill(self, note: dict[str, str], candidate: StoredCandidate) -> None:
        fields = self._fields
        meaning = candidate.meaning
        if fields.target:
            note[fields.target] = candidate.lemma
        if fields.meaning:
            note[fields.meaning] = self._highlight(meaning.meaning if meaning else None, candidate)
        if fields.ipa:
            note[fields.ipa] = (meaning.ipa if meaning else None) or ""
        if fields.translation and meaning and meaning.translation:
            note[fields.translation] = self._highlight(meaning.translation, candidate)
        if fields.synonyms and meaning and meaning.synonyms:
            note[fields.synonyms] = self._highlight(meaning.synonyms, candidate)
        if fields.examples and meaning and meaning.examples:
            note[fields.examples] = format_examples_as_list(
                self._highlight(meaning.examples, candidate)
            )
        self._fill_media(note, candidate)

    def _fill_media(self, note: dict[str, str], candidate: StoredCandidate) -> None:
        fields = self._fields
        media = candidate.media
        meaning_image = candidate.meaning_image
        voice = candidate.pronunciation
        tts = candidate.tts
        image, sound = self._media.image, self._media.sound
        sources: list[tuple[str, str | None, Callable[[str | None], str | None]]] = [
            (fields.image, media.screenshot_path if media else None, image),
            (fields.meaning_image, meaning_image.image_path if meaning_image else None, image),
            (fields.audio, media.audio_path if media else None, sound),
            (fields.audio_target_us, voice.us_audio_path if voice else None, sound),
            (fields.audio_target_uk, voice.uk_audio_path if voice else None, sound),
            (fields.audio_tts, tts.audio_path if tts else None, sound),
        ]
        for name, path, render in sources:
            if name and (value := render(path)):
                note[name] = value

    @staticmethod
    def _highlight(text: str | None, candidate: StoredCandidate) -> str:
        if not text:
            return ""
        return highlight_all_forms(text, candidate.lemma, candidate.surface_form)


class RecognitionNoteBuilder:
    """Fields of a recognition note: the phrase with the target in bold, in the user's fields."""

    def __init__(self, fields: AnkiFieldNames, media: NoteMedia) -> None:
        self._fields = fields
        self._content = _CardContent(fields, media)

    def build(self, candidate: StoredCandidate) -> dict[str, str]:
        note: dict[str, str] = {}
        if self._fields.sentence:
            note[self._fields.sentence] = highlight_all_forms(
                candidate.card_phrase, candidate.lemma, candidate.surface_form,
            )
        self._content.fill(note, candidate)
        return note


class ClozeNoteBuilder:
    """Fields of a cloze note: the phrase with the hidden words as an Anki gap, plus its hint.

    The rest of the note is filled the same way as a recognition note.
    """

    def __init__(self, builder: ClozeBuilder, fields: AnkiFieldNames, media: NoteMedia) -> None:
        self._builder = builder
        self._fields = fields
        self._content = _CardContent(fields, media)

    def build(self, candidate: StoredCandidate, cloze: CandidateCloze) -> dict[str, str]:
        indices = cloze.hidden_word_indices
        hidden = self._builder.hidden_words(cloze.phrase, indices)
        kind = cloze.hint_kind
        if kind not in self._builder.available_hints(candidate.meaning, hidden):
            kind = ClozeHintKind.NONE
        note: dict[str, str] = {}
        if self._fields.sentence:
            note[self._fields.sentence] = self._builder.cloze_text(cloze.phrase, indices)
        if self._fields.hint:
            note[self._fields.hint] = self._builder.hint_text(
                kind, candidate.meaning, hidden, cloze.custom_hint,
            )
        self._content.fill(note, candidate)
        return note
