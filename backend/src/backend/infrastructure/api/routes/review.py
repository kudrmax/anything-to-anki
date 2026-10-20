from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.document_dtos import SourceDocumentDTO  # noqa: TC001
from backend.application.dto.generation_dtos import GenerationStatusDTO  # noqa: TC001
from backend.application.dto.source_dtos import CardDTO, ReviewDTO  # noqa: TC001
from backend.domain.exceptions import (
    CollectionNotFoundError,
    GenerationBlockedError,
    GenerationNotSupportedError,
    ScopeNotReviewableError,
    SourceNotFoundError,
    SourceOperationBusyError,
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
from backend.domain.value_objects.generation_kind import (
    GenerationKind,  # noqa: TC001 — FastAPI parses it at runtime
)
from backend.domain.value_objects.generation_scope import (
    GenerationScope,  # noqa: TC001 — FastAPI parses it at runtime
)
from backend.infrastructure.api.dependencies import get_container, get_db_session
from backend.infrastructure.api.scope_param import parse_scope

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

    from backend.domain.value_objects.source_scope import SourceScope
    from backend.infrastructure.container import Container

router = APIRouter(prefix="/review", tags=["review"])


def review_scope(raw: str) -> SourceScope:
    """The set of sources a review request names; a bad token is a 400."""
    return parse_scope(raw)


@contextmanager
def _scope_errors() -> Iterator[None]:
    """A set that is not for review is a 400; a source or collection that is gone, a 404."""
    try:
        yield
    except ScopeNotReviewableError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (SourceNotFoundError, CollectionNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("")
def get_review(
    scope: str = "all",
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> ReviewDTO:
    with _scope_errors():
        return container.get_review_use_case(session).execute(review_scope(scope), sort)


@router.get("/candidates")
def get_review_candidates(
    scope: str = "all",
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[CardDTO]:
    with _scope_errors():
        return container.get_candidates_use_case(session).execute(review_scope(scope), sort)


@router.get("/documents")
def get_review_documents(
    scope: str = "all",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> list[SourceDocumentDTO]:
    """The texts of the set's sources in the set's order, with the targets to mark."""
    with _scope_errors():
        return container.get_review_documents_use_case(session).execute(review_scope(scope))


@router.get("/generation")
def get_generation_status(
    scope: str = "all",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> GenerationStatusDTO:
    """How far every kind of background generation got for the set's cards."""
    with _scope_errors():
        return container.get_generation_status_use_case(session).execute(review_scope(scope))


@router.post("/generation/{kind}", status_code=202)
def run_generation(
    kind: GenerationKind,
    cards: GenerationScope,
    scope: str = "all",
    sort: CandidateSortOrder = CandidateSortOrder.RELEVANCE,
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Queue one kind of generation for the set's `cards`, in the `sort` order. Sources
    that can't run it now are skipped; it fails only when none of them could."""
    with _scope_errors():
        try:
            enqueued = container.run_generation_use_case(session).execute(
                review_scope(scope), kind, cards, sort_order=sort,
            )
        except GenerationNotSupportedError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except (GenerationBlockedError, SourceOperationBusyError) as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
    session.commit()
    return {"enqueued": enqueued}


@router.post("/generation/{kind}/cancel")
def cancel_generation(
    kind: GenerationKind,
    scope: str = "all",
    session: Session = Depends(get_db_session),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, int]:
    """Cancel queued and running jobs of one kind of generation on every source of the set."""
    with _scope_errors():
        cancelled = container.cancel_generation_use_case(session).execute(
            review_scope(scope), kind,
        )
    session.commit()
    return {"cancelled": cancelled}
