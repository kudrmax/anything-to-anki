from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.domain.exceptions import (
    GenerationAlreadyRunningError,
    SourceNotFoundError,
    SourceNotTopicError,
    SourceOperationBusyError,
    TopicTargetsAlreadyGeneratedError,
)
from backend.infrastructure.api.dependencies import use_case
from backend.infrastructure.container import Container

if TYPE_CHECKING:
    from backend.application.use_cases.enqueue_topic_generation import (
        EnqueueTopicGenerationUseCase,
    )

logger = logging.getLogger(__name__)

router = APIRouter(tags=["generation"])


@router.post("/sources/{source_id}/topic-targets/generate", status_code=202)
def enqueue_topic_generation(
    source_id: int,
    enqueue: EnqueueTopicGenerationUseCase = Depends(  # noqa: B008
        use_case(Container.enqueue_topic_generation_use_case),  # noqa: B008
    ),
) -> dict[str, str]:
    """Enqueue the AI step of a topic source: turning its request into targets."""
    try:
        enqueue.execute(source_id)
    except SourceNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except SourceNotTopicError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (
        TopicTargetsAlreadyGeneratedError, GenerationAlreadyRunningError, SourceOperationBusyError,
    ) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"status": "queued"}
