from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.domain.value_objects.content import Kind, VideoRef
    from backend.domain.value_objects.document import Document
    from backend.domain.value_objects.format import Format


@dataclass(frozen=True)
class SourceDraft:
    """A source about to be made: everything but its title and collection.

    `own_title` is what the source is called when added alone; `label` says where it came
    from (a file name, a book's chapter).
    """

    document: Document
    kind: Kind
    source_format: Format
    own_title: str | None
    label: str
    words: int
    video: VideoRef | None = None
