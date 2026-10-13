from __future__ import annotations

from typing import TYPE_CHECKING

from backend.application.dto.document_dtos import (
    BlockDTO,
    DocumentPositionDTO,
    HighlightDTO,
    LineDTO,
    SourceDocumentDTO,
)
from backend.domain.exceptions import SourceHasNoDocumentError
from backend.domain.services.document_layout import DocumentLayout
from backend.domain.value_objects.document import Heading, ListItem, Paragraph

if TYPE_CHECKING:
    from backend.domain.entities.stored_candidate import StoredCandidate
    from backend.domain.ports.candidate_repository import CandidateRepository
    from backend.domain.ports.document_repository import DocumentRepository
    from backend.domain.value_objects.document import Block, Line


class GetSourceDocumentUseCase:
    """The document of a source for its screen, with the targets to mark in it.

    Where marks would overlap, the one that starts first stays; of two starting together,
    the longer one (a phrasal verb rather than its verb).
    """

    def __init__(
        self, document_repo: DocumentRepository, candidate_repo: CandidateRepository,
    ) -> None:
        self._document_repo = document_repo
        self._candidate_repo = candidate_repo

    def execute(self, source_id: int) -> SourceDocumentDTO:
        document = self._document_repo.get(source_id)
        if document is None:
            raise SourceHasNoDocumentError(source_id)
        layout = DocumentLayout(document)
        placed = sorted(
            (
                (layout.span(c.target_position), c)
                for c in self._candidate_repo.get_by_source(source_id)
                if c.target_position is not None and c.id is not None
            ),
            key=lambda pair: (pair[0][0], -pair[0][1], pair[1].id or 0),
        )
        highlights: list[HighlightDTO] = []
        taken_until = -1
        for (start, end), candidate in placed:
            if start < taken_until:
                continue
            highlights.append(_highlight(candidate))
            taken_until = end
        return SourceDocumentDTO(
            blocks=[_block(block) for block in document.blocks], highlights=highlights,
        )


def _highlight(candidate: StoredCandidate) -> HighlightDTO:
    assert candidate.id is not None and candidate.target_position is not None
    return HighlightDTO(
        candidate_id=candidate.id,
        position=DocumentPositionDTO.from_position(candidate.target_position),
        cefr_level=candidate.cefr_level,
        is_phrasal_verb=candidate.is_phrasal_verb,
    )


def _block(block: Block) -> BlockDTO:
    match block:
        case Heading():
            return BlockDTO(type="heading", lines=[LineDTO(text=block.text)], level=block.level)
        case Paragraph():
            return BlockDTO(
                type="paragraph", lines=_lines(block.lines), mode=block.mode.value,
            )
        case ListItem():
            return BlockDTO(
                type="list_item",
                lines=_lines(block.lines),
                ordered=block.ordered,
                depth=block.depth,
            )


def _lines(lines: tuple[Line, ...]) -> list[LineDTO]:
    return [LineDTO(text=line.text) for line in lines]
