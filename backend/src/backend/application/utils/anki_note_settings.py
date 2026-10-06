from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.ports.settings_repository import SettingsRepository

RECOGNITION_NOTE_TYPE_SETTING = "anki_note_type"
CLOZE_NOTE_TYPE_SETTING = "anki_cloze_note_type"
DEFAULT_RECOGNITION_NOTE_TYPE = "AnythingToAnkiType"
DEFAULT_CLOZE_NOTE_TYPE = "AnythingToAnkiCloze"

FIELD_SENTENCE_SETTING = "anki_field_sentence"
FIELD_TARGET_SETTING = "anki_field_target_word"
FIELD_MEANING_SETTING = "anki_field_meaning"
FIELD_IPA_SETTING = "anki_field_ipa"
FIELD_TRANSLATION_SETTING = "anki_field_translation"
FIELD_SYNONYMS_SETTING = "anki_field_synonyms"
FIELD_EXAMPLES_SETTING = "anki_field_examples"
FIELD_IMAGE_SETTING = "anki_field_image"
FIELD_MEANING_IMAGE_SETTING = "anki_field_meaning_image"
FIELD_AUDIO_SETTING = "anki_field_audio"
FIELD_AUDIO_TARGET_US_SETTING = "anki_field_audio_target_us"
FIELD_AUDIO_TARGET_UK_SETTING = "anki_field_audio_target_uk"
FIELD_AUDIO_TTS_SETTING = "anki_field_audio_tts"

ANKI_FIELD_DEFAULTS: dict[str, str] = {
    FIELD_SENTENCE_SETTING: "Sentence",
    FIELD_TARGET_SETTING: "Target",
    FIELD_MEANING_SETTING: "Meaning",
    FIELD_IPA_SETTING: "IPA",
    FIELD_TRANSLATION_SETTING: "Translation",
    FIELD_SYNONYMS_SETTING: "Synonyms",
    FIELD_EXAMPLES_SETTING: "Examples",
    FIELD_IMAGE_SETTING: "Image",
    FIELD_MEANING_IMAGE_SETTING: "MeaningImage",
    FIELD_AUDIO_SETTING: "Audio",
    FIELD_AUDIO_TARGET_US_SETTING: "AudioTargetUS",
    FIELD_AUDIO_TARGET_UK_SETTING: "AudioTargetUK",
    FIELD_AUDIO_TTS_SETTING: "AudioTTS",
}

ANKI_NOTE_TYPE_DEFAULTS: dict[str, str] = {
    RECOGNITION_NOTE_TYPE_SETTING: DEFAULT_RECOGNITION_NOTE_TYPE,
    CLOZE_NOTE_TYPE_SETTING: DEFAULT_CLOZE_NOTE_TYPE,
}


@dataclass(frozen=True)
class AnkiFieldNames:
    """Names of the note fields each part of a card goes to; an empty name leaves the part out.

    Both note types share them. The cloze type puts the phrase with its gaps
    into the same sentence field; the hint lives inside each gap.
    `image` is the video frame of the phrase, `meaning_image` a picture of
    the target that shows its meaning.
    """

    sentence: str
    target: str
    meaning: str
    ipa: str
    translation: str
    synonyms: str
    examples: str
    image: str
    meaning_image: str
    audio: str
    audio_target_us: str
    audio_target_uk: str
    audio_tts: str

    @staticmethod
    def read(settings_repo: SettingsRepository) -> AnkiFieldNames:
        def name(key: str) -> str:
            default = ANKI_FIELD_DEFAULTS[key]
            return settings_repo.get(key, default) or default

        return AnkiFieldNames(
            sentence=name(FIELD_SENTENCE_SETTING),
            target=name(FIELD_TARGET_SETTING),
            meaning=name(FIELD_MEANING_SETTING),
            ipa=name(FIELD_IPA_SETTING),
            translation=name(FIELD_TRANSLATION_SETTING),
            synonyms=name(FIELD_SYNONYMS_SETTING),
            examples=name(FIELD_EXAMPLES_SETTING),
            image=name(FIELD_IMAGE_SETTING),
            meaning_image=name(FIELD_MEANING_IMAGE_SETTING),
            audio=name(FIELD_AUDIO_SETTING),
            audio_target_us=name(FIELD_AUDIO_TARGET_US_SETTING),
            audio_target_uk=name(FIELD_AUDIO_TARGET_UK_SETTING),
            audio_tts=name(FIELD_AUDIO_TTS_SETTING),
        )

    def recognition_fields(self) -> list[str]:
        """Field names in the order a newly created recognition note type lists them."""
        return _present([self.sentence, *self._content_fields()])

    def cloze_fields(self) -> list[str]:
        """Field names in the order a newly created cloze note type lists them."""
        return _present([self.sentence, *self._content_fields()])

    def placeholders(self) -> dict[str, str]:
        """Field name for each `%FIELD_X%` placeholder of the card templates."""
        return {
            "FIELD_SENTENCE": self.sentence,
            "FIELD_TARGET": self.target,
            "FIELD_MEANING": self.meaning,
            "FIELD_IPA": self.ipa,
            "FIELD_TRANSLATION": self.translation,
            "FIELD_SYNONYMS": self.synonyms,
            "FIELD_EXAMPLES": self.examples,
            "FIELD_IMAGE": self.image,
            "FIELD_MEANING_IMAGE": self.meaning_image,
            "FIELD_AUDIO": self.audio,
            "FIELD_AUDIO_TARGET_US": self.audio_target_us,
            "FIELD_AUDIO_TARGET_UK": self.audio_target_uk,
            "FIELD_AUDIO_TTS": self.audio_tts,
        }

    def _content_fields(self) -> list[str]:
        return [
            self.target, self.meaning, self.ipa,
            self.translation, self.synonyms, self.examples,
            self.image, self.meaning_image, self.audio,
            self.audio_target_us, self.audio_target_uk, self.audio_tts,
        ]


@dataclass(frozen=True)
class AnkiNoteSettings:
    """Where cards go in Anki: the two note types and the fields they share."""

    recognition_note_type: str
    cloze_note_type: str
    fields: AnkiFieldNames

    @staticmethod
    def read(settings_repo: SettingsRepository) -> AnkiNoteSettings:
        def note_type(key: str) -> str:
            default = ANKI_NOTE_TYPE_DEFAULTS[key]
            return settings_repo.get(key, default) or default

        return AnkiNoteSettings(
            recognition_note_type=note_type(RECOGNITION_NOTE_TYPE_SETTING),
            cloze_note_type=note_type(CLOZE_NOTE_TYPE_SETTING),
            fields=AnkiFieldNames.read(settings_repo),
        )


def _present(names: list[str]) -> list[str]:
    return [name for name in names if name]
