from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.document_dtos import SourceDocumentDTO
from backend.application.utils.review_text import block_dto, highlights
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.services.text_chunks import list_numbers

if TYPE_CHECKING:
    from backend.application.utils.source_scope_resolver import SourceScopeResolver
    from backend.domain.entities.source import Source
    from backend.domain.ports.card_query import CardQuery
    from backend.domain.ports.card_state_query import CardStateQuery
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.value_objects.source_scope import SourceScope


class GetReviewDocumentsUseCase:
    """The documents of a set's sources for its review screen, in the set's order, each with
    the targets of its cards — the shown phrases — to mark in it, as `marks_shown` keeps
    them. A source without a document is left out.
    """

    def __init__(
        self,
        scope_resolver: SourceScopeResolver,
        document_repo: DocumentRepository,
        card_query: CardQuery,
        card_state_query: CardStateQuery,
    ) -> None:
        self._scope_resolver = scope_resolver
        self._document_repo = document_repo
        self._card_query = card_query
        self._card_state_query = card_state_query

    def execute(self, scope: SourceScope) -> list[SourceDocumentDTO]:
        documents = (
            self._document(source) for source in self._scope_resolver.reviewable_sources(scope)
        )
        return [document for document in documents if document is not None]

    def _document(self, source: Source) -> SourceDocumentDTO | None:
        assert source.id is not None
        source_id = source.id
        document = self._document_repo.get(source_id)
        if document is None:
            return None
        layout = DocumentLayout(document)
        numbers = list_numbers(document.blocks)
        return SourceDocumentDTO(
            source_id=source_id,
            title=source.title or "",
            blocks=[
                block_dto(block, number) for block, number in zip(
                    document.blocks, numbers, strict=True,
                )
            ],
            highlights=highlights(
                layout,
                self._card_query.shown_places(source_id),
                self._card_state_query.done_of_sources([source_id]),
            ),
        )
