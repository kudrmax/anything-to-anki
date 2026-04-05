from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.domain.entities.prompt_template import PromptTemplate
from backend.domain.exceptions import PromptNotFoundError
from backend.domain.ports.prompt_repository import PromptRepository
from backend.infrastructure.persistence.models import PromptTemplateModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SqlaPromptRepository(PromptRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_key(self, function_key: str) -> PromptTemplate | None:
        row = self._session.execute(
            select(PromptTemplateModel).where(PromptTemplateModel.function_key == function_key)
        ).scalar_one_or_none()
        return row.to_entity() if row is not None else None

    def list_all(self) -> list[PromptTemplate]:
        rows = self._session.execute(select(PromptTemplateModel)).scalars().all()
        return [row.to_entity() for row in rows]

    def update(self, function_key: str, system_prompt: str, user_template: str) -> PromptTemplate:
        row = self._session.execute(
            select(PromptTemplateModel).where(PromptTemplateModel.function_key == function_key)
        ).scalar_one_or_none()
        if row is None:
            raise PromptNotFoundError(function_key)
        row.system_prompt = system_prompt
        row.user_template = user_template
        return row.to_entity()
