from __future__ import annotations

from pydantic import BaseModel

from backend.domain.value_objects.document_position import DocumentPosition


class DocumentPositionDTO(BaseModel):
    """A piece of one block of a source's document; characters in code points, end exclusive."""

    block: int
    start_line: int
    start_char: int
    end_line: int
    end_char: int

    @staticmethod
    def from_position(position: DocumentPosition) -> DocumentPositionDTO:
        return DocumentPositionDTO(
            block=position.block,
            start_line=position.start_line,
            start_char=position.start_char,
            end_line=position.end_line,
            end_char=position.end_char,
        )

    def to_position(self) -> DocumentPosition:
        return DocumentPosition(
            block=self.block,
            start_line=self.start_line,
            start_char=self.start_char,
            end_line=self.end_line,
            end_char=self.end_char,
        )
