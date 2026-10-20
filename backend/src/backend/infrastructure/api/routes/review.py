from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from backend.application.dto.document_dtos import SourceDocumentDTO  # noqa: TC001
from backend.application.dto.source_dtos import CardDTO, ReviewDTO  # noqa: TC001
from backend.domain.exceptions import (
    CollectionNotFoundError,
    ScopeNotReviewableError,
    SourceNotFoundError,
)
from backend.domain.value_objects.candidate_sort_order import CandidateSortOrder
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
