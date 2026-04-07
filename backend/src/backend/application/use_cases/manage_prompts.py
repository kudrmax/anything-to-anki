from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.prompt_dtos import PromptTemplateDTO, UpdatePromptRequest
from backend.domain.exceptions import PromptNotFoundError

if TYPE_CHECKING:
    from backend.domain.entities.prompt_template import PromptTemplate
    from backend.domain.ports.prompt_repository import PromptRepository


def _to_dto(pt: PromptTemplate) -> PromptTemplateDTO:
    return PromptTemplateDTO(
        id=pt.id,
        function_key=pt.function_key,
        system_prompt=pt.system_prompt,
        user_template=pt.user_template,
    )


class ManagePromptsUseCase:
    """List and update prompt templates.

    Functions are defined by the system; only text is editable.
    """

    def __init__(self, prompt_repo: PromptRepository) -> None:
        self._prompt_repo = prompt_repo

    def list_all(self) -> list[PromptTemplateDTO]:
        return [_to_dto(pt) for pt in self._prompt_repo.list_all()]

    def update(self, function_key: str, request: UpdatePromptRequest) -> PromptTemplateDTO:
        existing = self._prompt_repo.get_by_key(function_key)
        if existing is None:
            raise PromptNotFoundError(function_key)
        updated = self._prompt_repo.update(
            function_key=function_key,
            system_prompt=request.system_prompt,
            user_template=request.user_template,
        )
        return _to_dto(updated)
