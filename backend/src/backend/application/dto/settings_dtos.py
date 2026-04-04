from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator

from backend.domain.value_objects.cefr_level import CEFRLevel


class SettingsDTO(BaseModel):
    """Application settings."""

    cefr_level: str
    anki_deck_name: str


class UpdateSettingsRequest(BaseModel):
    """Input for updating settings. At least one field must be provided."""

    cefr_level: str | None = None
    anki_deck_name: str | None = None

    @field_validator("cefr_level")
    @classmethod
    def validate_cefr_level(cls, v: str | None) -> str | None:
        if v is not None:
            CEFRLevel.from_str(v)
            return v.strip().upper()
        return v

    @model_validator(mode="after")
    def at_least_one_field(self) -> UpdateSettingsRequest:
        if self.cefr_level is None and self.anki_deck_name is None:
            raise ValueError("At least one of cefr_level or anki_deck_name must be provided")
        return self
