from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.exceptions import PromptNotFoundError
from backend.infrastructure.api.dependencies import get_container, get_db_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.application.dto.prompt_dtos import PromptTemplateDTO, UpdatePromptRequest
    from backend.infrastructure.container import Container

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("")
def list_prompts(
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[PromptTemplateDTO]:
    return container.manage_prompts_use_case(session).list_all()


@router.put("/{function_key}")
def update_prompt(
    function_key: str,
    body: UpdatePromptRequest,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> PromptTemplateDTO:
    try:
        result = container.manage_prompts_use_case(session).update(function_key, body)
        session.commit()
        return result
    except PromptNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
