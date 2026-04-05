from __future__ import annotations

from pydantic import BaseModel, model_validator


class PromptTemplateDTO(BaseModel):
    """Read model for a prompt template."""

    id: int
    function_key: str
    name: str
    description: str
    system_prompt: str
    user_template: str


class UpdatePromptRequest(BaseModel):
    """Request to update the text of a prompt template."""

    system_prompt: str
    user_template: str

    @model_validator(mode="after")
    def _not_blank(self) -> UpdatePromptRequest:
        if not self.system_prompt.strip():
            raise ValueError("system_prompt must not be blank")
        if not self.user_template.strip():
            raise ValueError("user_template must not be blank")
        return self
