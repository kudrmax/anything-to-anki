from __future__ import annotations

from pydantic import BaseModel, field_validator

from backend.domain.value_objects.cefr_level import CEFRLevel


class SettingsDTO(BaseModel):
    """Application settings."""

    cefr_level: str


class UpdateSettingsRequest(BaseModel):
    """Input for updating settings."""

    cefr_level: str

    @field_validator("cefr_level")
    @classmethod
    def validate_cefr_level(cls, v: str) -> str:
        CEFRLevel.from_str(v)
        return v.strip().upper()
