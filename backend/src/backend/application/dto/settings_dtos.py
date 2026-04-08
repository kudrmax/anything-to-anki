from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator

from backend.domain.value_objects.cefr_level import CEFRLevel


class SettingsDTO(BaseModel):
    """Application settings."""

    cefr_level: str
    anki_deck_name: str
    ai_provider: str
    ai_model: str
    anki_note_type: str
    anki_field_sentence: str
    anki_field_target_word: str
    anki_field_meaning: str
    anki_field_ipa: str
    anki_field_image: str
    anki_field_audio: str
    anki_field_translation: str
    anki_field_synonyms: str
    enable_definitions: bool


class UpdateSettingsRequest(BaseModel):
    """Input for updating settings. At least one field must be provided."""

    cefr_level: str | None = None
    anki_deck_name: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    anki_note_type: str | None = None
    anki_field_sentence: str | None = None
    anki_field_target_word: str | None = None
    anki_field_meaning: str | None = None
    anki_field_ipa: str | None = None
    anki_field_image: str | None = None
    anki_field_audio: str | None = None
    anki_field_translation: str | None = None
    anki_field_synonyms: str | None = None
    enable_definitions: bool | None = None

    @field_validator("cefr_level")
    @classmethod
    def validate_cefr_level(cls, v: str | None) -> str | None:
        if v is not None:
            CEFRLevel.from_str(v)
            return v.strip().upper()
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdateSettingsRequest:
        values = [getattr(self, f) for f in type(self).model_fields]
        if all(v is None for v in values):
            raise ValueError("At least one field must be provided")
        return self
